#-*- coding: utf8 -*-

import configparser, msvcrt, os, shutil, subprocess, sys
from subprocess import Popen, PIPE, STDOUT

import ptupdata, ptuplibs
from utils import print_ok, print_warn, print_err

SCRIPT_VERSION = '2.0'

# -----------------------------------------------------------------------
QMAKE_CMD = ['qmake']
MAKE_CMD  = ['mingw32-make']
HG_CMD    = ['hg']
ISCC_CMD  = ['iscc']
ZIP_CMD   = ['7z', 'a']

ARCHIVE_DIR   = ''
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))

PTBASEDIR   = 0      # Photivo repo base dir (where photivo.pro is)
PKGBASEDIR  = 1      # base dir for building
TSHOOTDIR   = 2      # dir for troubleshooter
BUILDDIR    = 3      # dir where compiling is done
BINDIR      = 4      # dir for finished binaries and data files
ISSFILE     = 5      # installer script file
CHLOGFILE   = 6      # Changelog.txt file
DATESTYFILE = 7      # Hg shortdate style file
VERSTYFILE  = 8      # Hg revision/version style file

class Arch:
    win32 = 0
    win64 = 1
    archs = [0, 1]

class ArchNames
    win32 = 'win32'
    win64 = 'win64'
    names = ['win32', 'win64']
    bits  = ['32', '64']

DIVIDER = '------------------------------------------------------------------------------'

# =======================================================================

def main():
    print('\nPhotivo for Windows package builder', SCRIPT_VERSION)
    print(DIVIDER, end='\n\n')

    if not os.path.isfile(os.path.join(os.getcwd(), 'photivo.pro')):
        print_err('ERROR: Photivo repository not found. Please run this script from the folder')
        print_err('where "photivo.pro" is located.')
        return False

    # setup, config and pre-build checks
    load_ini_file()

    paths = build_paths(os.getcwd())

    if not check_build_env(paths): return False
    if not prepare_dirs(paths): return False

    # build and package everything
    builder = PhotivoBuilder()
    if not builder.build(Arch.win32): return False
    if not builder.build(Arch.win64): return False
    if not builder.package(): return False

    # final summary and option to clean up
    if not builder.show_summary(): return False

    print('Everything looks fine. You can test and upload the release now.')
    print('\nAfterwards I can clean up automatically, i.e.:')

    if ARCHIVE_DIR == '':
        print('* delete everything created during the build process except')
        print('  the two installers')
    else:
        print('* move installers to', ARCHIVE_DIR)
        print('* delete everything else created during the build process')

    if wait_for_yesno('\nShall I clean up now?'):
        if not cleanup(): return False
    else:
        print('OK. The mess stays.')

    print_ok('All done.')
    return True


# -----------------------------------------------------------------------
# Returns a nested list of all needed dir and file paths
def build_paths(repo_dir):
    repo_dir = os.path.abspath(repo_dir)
    base_dir = os.path.join(repo_dir, 'build-for-release')

    return [
        repo_dir,                           # PTBASEDIR
        base_dir,                           # PKGBASEDIR
        os.path.join(base_dir, TSHOOTDIR),  # TSHOOTDIR
        [   # BUILDDIR
            os.path.join(base_dir, 'build-' + ArchNames.win32),
            os.path.join(base_dir, 'build-' + ArchNames.win64)
        ],[ # BINDIR
            os.path.join(base_dir, 'bin-' + ArchNames.win32),
            os.path.join(base_dir, 'bin-' + ArchNames.win64)
        ],[ # ISSFILE
            os.path.join(SCRIPT_DIR, '..', 'win-installer', 'photivo-setup-' + ArchNames.win32 + '.iss'),
            os.path.join(SCRIPT_DIR, '..', 'win-installer', 'photivo-setup-' + ArchNames.win64 + '.iss')
        ],
        os.path.join(repo_dir, 'Changelog.txt')           # CHLOGFILE
        os.path.join(SCRIPT_DIR, 'hg-shortdate.style'),   # DATESTYFILE
        os.path.join(SCRIPT_DIR, 'hg-revdatenum.style')   # VERSTYFILE
    ]


# -----------------------------------------------------------------------
def check_build_env(paths):
    # Force English output from Mercurial
    os.environ['HGPLAIN'] = 'true'

    # Check presence of required commands
    cmds_ok = check_bin(QMAKE_CMD[0])
    cmds_ok = check_bin(MAKE_CMD[0]) and cmds_ok
    cmds_ok = check_bin(HG_CMD[0]) and cmds_ok
    cmds_ok = check_bin(ISCC_CMD[0]) and cmds_ok
    cmds_ok = check_bin(ZIP_CMD[0]) and cmds_ok
    if not cmds_ok: return false

    hgbranch = get_cmd_output(HG_CMD + ['branch'])
    if hgbranch != 'default':
        print_warn('Working copy is set to branch "%s" instead of "default".'%(hgbranch))
        if not wait_for_yesno('Continue anyway?'):
            return False

    # Working copy should be clean. The only exception is the Changelog.txt file.
    # Ignoring that makes it possible to start the release script and edit the
    # changelos while it is running.
    if not 'commit: (clean)' in get_cmd_output(HG_CMD + ["summary"]):
        hgstatus = get_cmd_output(HG_CMD + ["status"]).split('\n')
        for file_entry in hgstatus:
            if (len(file_entry) > 0) and (not 'Changelog.txt' in file_entry):
                print_warn('Working copy has uncommitted changes.')
                if wait_for_yesno('Continue anyway?'):
                    break
                else:
                    return False

    files_ok = True

    # Installer script files must be present
    if not os.path.isfile(paths[ISSFILE][Arch.win32]):
        print_err('ERROR: Installer script "%s" missing.'%paths[ISSFILE][Arch.win32])
        files_ok = False

    if not os.path.isfile(paths[ISSFILE][Arch.win64]):
        print_err('ERROR: Installer script "%s" missing.'%paths[ISSFILE][Arch.win64])
        files_ok = False

    if not os.path.isfile(paths[DATESTYFILE]):
        print_err('ERROR: Style file "%s" missing.'%paths[DATESTYFILE])
        files_ok = False

    if not os.path.isfile(paths[VERSTYFILE]):
        print_err('ERROR: Style file "%s" missing.'%paths[VERSTYFILE])
        files_ok = False

    return files_ok


# -----------------------------------------------------------------------
def load_ini_file():
    ini_path = os.path.splitext(__file__)[0] + '.ini'

    if not os.path.exists(ini_path):
        return

    global QMAKE_CMD
    global MAKE_CMD
    global HG_CMD
    global ISCC_CMD
    global ZIP_CMD
    global ARCHIVE_DIR

    config = configparser.ConfigParser(ini_path)

    if 'commands' in config:
        if 'qmake'   in config['commands']: QMAKE_CMD   = config['commands']['qmake']
        if 'make'    in config['commands']: MAKE_CMD    = config['commands']['make']
        if 'hg'      in config['commands']: HG_CMD      = config['commands']['hg']
        if 'iscc'    in config['commands']: ISCC_CMD    = config['commands']['iscc']
        if 'zip'     in config['commands']: ZIP_CMD     = config['commands']['zip']

    if 'paths' in config:
        if 'archive' in config['paths']:    ARCHIVE_DIR = config['paths']['archive']


# -----------------------------------------------------------------------
def prepare_dirs(paths):
    try:
        if os.path.exists(paths[PKGBASEDIR]):
            shutil.rmtree(paths[PKGBASEDIR])

        os.makedirs(paths[PKGBASEDIR])
        os.makedir(paths[TSHOOTDIR])
        os.makedir(paths[BUILDDIR][Arch.win32])
        os.makedir(paths[BUILDDIR][Arch.win64])
        os.makedir(paths[BINDIR][Arch.win32])
        os.makedir(paths[BINDIR][Arch.win64])

        return True

    except OSError:
        print_err('ERROR: Setup of build directory tree "%s" failed.'%(builddir))
        return False


# -----------------------------------------------------------------------
# Tests if a command is present
# exec_cmd   string  command that should be tested
# <return>   bool    true if command can be executed
def check_bin(exec_cmd):
    with open(os.devnull, 'w') as devnull:
        try:
            proc.call(exec_cmd, stdout=devnull, stderr=devnull)
            return true
        except OSError:
            print_err('ERROR: Required command not found:', exec_cmd)
            return false


# -----------------------------------------------------------------------
def wait_for_yesno(msg):
    print(msg, end=' (y/n) ')
    sys.stdout.flush()

    while True:
        char = msvcrt.getch()

        if char == b'\x03':
            raise KeyboardInterrupt

        try:
            char = str(char, 'utf-8').lower()
        except UnicodeDecodeError:
            pass

        if char == 'y':
            print('Yes')
            return True
        elif char == 'n':
            print('No')
            return False


# -----------------------------------------------------------------------
def wait_for_key(keys):
    print(msg, end=' ')
    sys.stdout.flush()

    while True:
        char = msvcrt.getch()

        if char == b'\x03':
            raise KeyboardInterrupt

        try:
            char = str(char, 'utf-8').lower()
        except UnicodeDecodeError:
            pass

        if char == keys:
            print(char)
            return True


# -----------------------------------------------------------------------
def get_cmd_output(cmd):
    return subprocess.check_output(cmd, universal_newlines=True).strip()


# -----------------------------------------------------------------------
def run_cmd(cmd):
    return subprocess.call(cmd) == 0


# -----------------------------------------------------------------------
class PhotivoBuilder:
    _files = None
    _paths = None
    _hgbranch = None
    _release_date = None

    _INST_NAME_PATTERN = 'photivo-setup-%s-%s'
    _INSTALLERS = 0
    _TRSHOOTER  = 1

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def __init__(self, paths):
        self._paths = paths
        self._hgbranch = get_cmd_output(HG_CMD + ['branch'])
        self._release_date = get_cmd_output(HG_CMD + ['log', '-b', self._hgbranch, '-l', '1', \
                                            '--style', self._paths[DATESTYFILE]])
        self._files = [[ \
                          os.path.join(self._paths[PKGBASEDIR], self._INST_NAME_PATTERN%(self._release_date, ArchNames.win32) + '.exe'), \
                          os.path.join(self._paths[PKGBASEDIR], self._INST_NAME_PATTERN%(self._release_date, ArchNames.win64) + '.exe') \
                      ], \
                      os.path.join(self._paths[PKGBASEDIR], 'photivo-win3264-troubleshooter-%s.zip'%self._release_date)]

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def build(self, arch):
        try:
            os.chdir(self._paths[PKGBASEDIR])
        except OSError as err:
            print_err('ERROR: Changing directory to "%s" failed.'%self._paths[PKGBASEDIR])
            print_err(str(err))
            return False

        print_ok('Building Photivo and ptClear (%s) ...'%ArchNames.names[arch])

        # Build production Photivo
        build_result = run_cmd(QMAKE_CMD + [os.path.join('..', 'photivo.pro'), 'CONFIG+=WithoutGimp', 'CONFIG-=debug']) \
                       && run_cmd(MAKE_CMD)

        if not build_result \
           or not os.path.isfile(os.path.join(self._paths[BUILDDIR][arch], 'photivo.exe') \
           or not os.path.isfile(os.path.join(self._paths[BUILDDIR][arch], 'ptClear.exe') \
        :
            print_err('ERROR: Building Photivo failed.')
            return False

        try:
            shutil.move(os.path.join(self._paths[BUILDDIR][arch], 'photivo.exe'), self._paths[BINDIR][arch])
            shutil.copy(os.path.join(self._paths[BUILDDIR][arch], 'ptClear.exe'), self._paths[BINDIR][arch])
            os.remove(os.path.join(self._paths[BUILDDIR][arch], 'Objects', 'ptMain.o')
        except OSError as err:
            print_err('ERROR: Copying binaries to "%s" failed.'%self._paths[BINDIR])
            print_err(str(err))
            return False

        # Build the troubeshooter
        print_ok('Building troubeshooter (%s) ...'%ArchNames.names[arch])

        build_result = run_cmd(QMAKE_CMD + [os.path.join('..', 'photivo.pro'), \
                               'CONFIG+=WithoutGimp WithoutClear console', 'CONFIG-=debug']) \
                       && run_cmd(MAKE_CMD)

        if not build_result or not os.path.isfile(os.path.join(self._paths[BUILDDIR][arch], 'photivo.exe'):
            print_err('ERROR: Building troubleshooter failed.')
            return False

        try:
            shutil.move(os.path.join(self._paths[BUILDDIR][arch], 'photivo.exe'), \
                        os.path.join(self._paths[TSHOOTDIR][arch], 'ptConsole%s.exe'%ArchNames.bits[arch])
        except OSError as err:
            print_err('ERROR: Copying troubleshooter binary to "%s" failed.'%self._paths[TSHOOTDIR])
            print_err(str(err))
            return False

        return True

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def package(self):
        # update libs and data files in bin dir
        for arch in Arch.archs:
            print_ok('Packaging files (%s)...'%(ArchNames.names[arch]))
            if not ptuplibs.main(self._paths[PTBASEDIR], self._paths[BINDIR][arch], ArchNames.names[arch])
            if not ptupdata.main(self._paths[PTBASEDIR], self._paths[BINDIR][arch])

        # installer exes
        if not self._create_installers(): return False

        # TODO create tshooter zip

        return True

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def _create_installers(self):
        ptversion = get_cmd_output(HG_CMD + ['log', '-b', self._hgbranch, '-l', '1', '--style', self._paths[VERSTYFILE])

        for arch in Arch.archs:
            print_ok('Creating installer (%s) ...'%(ArchNames.names[arch]))

            with open(self._paths[ISSFILE][arch] as issfile:
                iss_script = issfile.readlines()

            i = 0
            while i < len(iss_script):
                line = iss_script[i].replace('{{versionstring}}', ptversion)
                line = line.replace('{{changelogfile}}', self._paths[CHLOGFILE])
                line = line.replace('{{outputbasename}}', self._INST_NAME_PATTERN%(self._release_date, ArchNames.names[arch])
                iss_script[i] = line.replace('{{bindir}}', self._paths[BINDIR])
                i += 1

            iscc_proc = Popen(ISCC_CMD + ['/O' + self._paths[PKGBASEDIR]], stdin=PIPE)
            iscc_proc.communicate(input=iss_script)

            if iscc_proc.returncode != 0:
                print_err('ERROR: Creating installer (%s) failed.'%(ArchNames.names[arch]))
                return False

        return True

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def show_summary(self):
        print('\n' + DIVIDER + 'Final status' + DIVIDER)

        print('The packages are located in:\n', paths[PKGBASEDIR])

        print('\nPhotivo installer 64bit: ', end='')
        inst64_ok = print_file_status(self._files[PhotivoBuilder._INSTALLERS][Arch.win64])

        print('Photivo installer 32bit: ', end='')
        inst32_ok = print_file_status(self._files[PhotivoBuilder._INSTALLERS][Arch.win32])

        print('Troubleshooter archive : ', end='')
        trshoot_ok = print_file_status(self._files[PhotivoBuilder._TRSHOOTER])

        print('\nChangeset info:')
        run_cmd(HG_CMD + ['log', '-b', self._hgbranch, '-l', '1'])

        print(DIVIDER)

        return inst64_ok and inst32_ok and trshoot_ok


# -----------------------------------------------------------------------
if __name__ == '__main__':
    try:
        sys.exit(0 if main() else 1)
    except KeyboardInterrupt:
        print_err('\nAborted by the user.')
        sys.exit(1)
