#-*- coding: utf8 -*-

import sys

if sys.hexversion < 0x03020000:
    print('ERROR: Your Python is too old. At least v3.2 needed. Yours is:')
    print(sys.version)
    sys.exit(1)

import configparser, msvcrt, os, shutil, subprocess
from subprocess import Popen, PIPE, STDOUT
from datetime import datetime

import ptupdata, ptuplibs
from utils import print_ok, print_warn, print_err

SCRIPT_VERSION = '2.0'

# -----------------------------------------------------------------------

QMAKE = 'qmake'
MAKE  = 'make'
HG    = 'hg'
ISCC  = 'iscc'
STRIP = 'strip'

CMD = {   # updated by load_ini_file()
    QMAKE : 'qmake',
    MAKE  : 'mingw32-make',
    HG    : 'hg',
    ISCC  : 'iscc',
    STRIP : 'strip'
}

# Some commands (like make) do not need parameters to stark working for real.
# These parameters are for check_bin() ensure that the programs will be
# executed if present but they will not attempt to do any real work.
CMD_PARAMS_FOR_TEST = {
    QMAKE : ['--version'],
    MAKE  : ['--version'],
    HG    : ['--version'],
    ISCC  : ['/?'],
    STRIP : ['--version']
}

ARCHIVE_DIR   = ''   # filled by load_ini_file()
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))

PTBASEDIR   = 0      # Photivo repo base dir (where photivo.pro is)
PKGBASEDIR  = 1      # base dir for building
BUILDDIR    = 2      # dir where compiling is done
BINDIR      = 3      # dir for finished binaries and data files
ISSFILE     = 4      # installer script file
CHLOGFILE   = 5      # Changelog.txt file
LICFILE     = 6      # COPYING file
LIC3FILE    = 7      # COPYING.3rd.party file
DATESTYFILE = 8      # Hg shortdate style file
VERSTYFILE  = 9      # Hg revision/version style file

class Arch:
    win32 = 0
    win64 = 1
    archs = [0, 1]

class ArchNames:
    win32 = 'win32'
    win64 = 'win64'
    names = ['win32', 'win64']
    bits  = ['32', '64']
    dirnames = []   # filled by load_ini_file()

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
    if not load_ini_file(): return False

    paths = build_paths(os.getcwd())

    if not check_build_env(paths): return False

    if not prepare_dirs(paths): return False

    # build and package everything
    builder = PhotivoBuilder(paths)

    for arch in Arch.archs:
        if not change_tc_arch(ArchNames.dirnames[arch]): return False
        if not builder.build(arch): return False
        if not builder.package(arch): return False

    # final summary and option to clean up
    if not builder.show_summary():
        print_err('Something went wrong along the way.')
        return False

    print_ok('Everything looks fine.')
    print('You can test and upload the release now.')
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
        [   # BUILDDIR
            os.path.join(base_dir, 'build-' + ArchNames.win32),
            os.path.join(base_dir, 'build-' + ArchNames.win64)
        ],[ # BINDIR
            os.path.join(base_dir, 'bin-' + ArchNames.win32),
            os.path.join(base_dir, 'bin-' + ArchNames.win64)
        ],[ # ISSFILE
            os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'win-installer', 'photivo-setup-' + ArchNames.win32 + '.iss')),
            os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'win-installer', 'photivo-setup-' + ArchNames.win64 + '.iss'))
        ],
        os.path.normpath(os.path.join(repo_dir, '..', 'Changelog.txt')),    # CHLOGFILE
        os.path.join(repo_dir, 'COPYING'),                # LICFILE
        os.path.join(repo_dir, 'COPYING.3rd.party'),      # LIC3FILE
        os.path.join(SCRIPT_DIR, 'hg-shortdate.style'),   # DATESTYFILE
        os.path.join(SCRIPT_DIR, 'hg-revdatenum.style')   # VERSTYFILE
    ]


# -----------------------------------------------------------------------
def check_build_env(paths):
    # Force English output from Mercurial
    os.environ['HGPLAIN'] = 'true'

    # Check presence of required commands
    cmds_ok = True
    for cmd in CMD:
        cmds_ok = check_bin([CMD[cmd]] + CMD_PARAMS_FOR_TEST[cmd]) and cmds_ok
    if not cmds_ok: return False

    hgbranch = get_cmd_output([CMD[HG], 'branch'])
    if hgbranch != 'default':
        print_warn('Working copy is set to branch "%s" instead of "default".'%(hgbranch))
        if not wait_for_yesno('Continue anyway?'):
            return False

    # Working copy should be clean. The only exception is the Changelog.txt file.
    # Ignoring that makes it possible to start the release script and edit the
    # changelos while it is running.
    if not 'commit: (clean)' in get_cmd_output([CMD[HG], 'summary']):
        hgstatus = get_cmd_output([CMD[HG], 'status']).split('\n')
        for file_entry in hgstatus:
            if (len(file_entry) > 0) and (not 'Changelog.txt' in file_entry):
                print_warn('Working copy has uncommitted changes.')
                if wait_for_yesno('Continue anyway?'):
                    break
                else:
                    return False

    files_ok = True

    # files must be present
    if not os.path.isfile(paths[ISSFILE][Arch.win32]):
        print_err('ERROR: Installer script "%s" missing.'%paths[ISSFILE][Arch.win32])
        files_ok = False

    if not os.path.isfile(paths[ISSFILE][Arch.win64]):
        print_err('ERROR: Installer script "%s" missing.'%paths[ISSFILE][Arch.win64])
        files_ok = False

    if not os.path.isfile(paths[CHLOGFILE]):
        print_err('ERROR: File "%s" missing.'%paths[CHLOGFILE])
        files_ok = False

    if not os.path.isfile(paths[LICFILE]):
        print_err('ERROR: File "%s" missing.'%paths[LICFILE])
        files_ok = False

    if not os.path.isfile(paths[LIC3FILE]):
        print_err('ERROR: File "%s" missing.'%paths[LIC3FILE])
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
    def err_msg():
        print_err('ERROR: Missing or incomplete config file (ptrelease.ini)!')
        print_err('Must at least contain section [paths] with entries "win32" and "win64".')

    ini_path = os.path.splitext(__file__)[0] + '.ini'

    if not os.path.exists(ini_path):
        err_msg()
        return False

    config = configparser.ConfigParser()
    config.read(ini_path)

    try:
        ArchNames.dirnames.append(config['paths']['win32'])
        ArchNames.dirnames.append(config['paths']['win64'])
    except KeyError:
        err_msg()
        return False

    global CMD
    global ARCHIVE_DIR

    if 'commands' in config:
        if QMAKE in config['commands']: CMD[QMAKE] = config['commands']['qmake']
        if MAKE  in config['commands']: CMD[MAKE]  = config['commands']['make']
        if HG    in config['commands']: CMD[HG]    = config['commands']['hg']
        if ISCC  in config['commands']: CMD[ISCC]  = config['commands']['iscc']
        if STRIP in config['commands']: CMD[STRIP] = config['commands']['strip']

    if 'archive' in config['paths']: ARCHIVE_DIR = config['paths']['archive']

    return True


# -----------------------------------------------------------------------
def prepare_dirs(paths):
    try:
        if os.path.exists(paths[PKGBASEDIR]):
            shutil.rmtree(paths[PKGBASEDIR])

        os.makedirs(paths[BUILDDIR][Arch.win32])
        os.makedirs(paths[BUILDDIR][Arch.win64])
        os.makedirs(paths[BINDIR][Arch.win32])
        os.makedirs(paths[BINDIR][Arch.win64])

        return True

    except OSError as err:
        print_err('ERROR: Setup of build directory tree "%s" failed.'%paths[PKGBASEDIR])
        print_err(str(err))
        return False


# -----------------------------------------------------------------------
def check_bin(exec_cmd):
    """Tests if a command is present
    exec_cmd   list    command that should be tested
    <return>   bool    true if command can be executed
    """
    with open(os.devnull, 'w') as devnull:
        try:
            subprocess.call(exec_cmd, stdout=devnull, stderr=devnull)
            return True
        except OSError:
            print_err('ERROR: Required command not found: ' + exec_cmd[0])
            return False


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
def wait_for_key(msg, keys):
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

        if char.lower() in keys:
            print(char)
            return char


# -----------------------------------------------------------------------
def change_tc_arch(dirname):
    try:
        if run_cmd(['chboth.bat', dirname], use_shell=True):
            return True
    except Exception as err:
        print_err(str(err))

    print_err('ERROR: Failed to switch toolchain to ' + dirname)
    return False


# -----------------------------------------------------------------------
def get_cmd_output(cmd):
    return subprocess.check_output(cmd, universal_newlines=True).strip()


# -----------------------------------------------------------------------
def run_cmd(cmd, use_shell=False):
    return subprocess.call(cmd, shell=use_shell) == 0


# -----------------------------------------------------------------------
def print_file_status(filepath):
    if os.path.isfile(filepath):
        print('OK')
        return True
    else:
        print('Error')
        return False

# -----------------------------------------------------------------------
class PhotivoBuilder:
    _install_files = None
    _paths = None
    _hgbranch = None
    _release_date = None

    _INST_NAME_PATTERN = 'photivo-setup-%s-%s'
    _INSTALLERS = 0

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def __init__(self, paths):
        self._paths = paths
        self._hgbranch = get_cmd_output([CMD[HG], 'branch'])
        self._release_date = get_cmd_output([CMD[HG], 'log', '-b', self._hgbranch, '-l', '1', \
                                            '--style', self._paths[DATESTYFILE]])
        self._install_files = [
            os.path.join(self._paths[PKGBASEDIR], self._INST_NAME_PATTERN%(self._release_date, ArchNames.win32) + '.exe'),
            os.path.join(self._paths[PKGBASEDIR], self._INST_NAME_PATTERN%(self._release_date, ArchNames.win64) + '.exe')
        ]

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def build(self, arch):
        """Build Photivo for the given architecture.
        arch            can be either Arch.win32 or Arch.win64
        <return>  bool  True if build succeeded, False otherwise
        """
        try:
            os.chdir(self._paths[BUILDDIR][arch])
        except OSError as err:
            print_err('ERROR: Changing directory to "%s" failed.'%self._paths[PKGBASEDIR])
            print_err(str(err))
            return False

        print_ok('Building Photivo and ptClear (%s) ...'%ArchNames.names[arch])

        # Build production Photivo
        build_result = run_cmd([CMD[QMAKE], \
                               os.path.join('..', '..', 'photivo.pro'), \
                               'CONFIG+=WithoutGimp', \
                               'CONFIG-=debug']) \
                       and run_cmd([CMD[MAKE]])

        if not build_result \
           or not os.path.isfile(os.path.join(self._paths[BUILDDIR][arch], 'photivo.exe')) \
           or not os.path.isfile(os.path.join(self._paths[BUILDDIR][arch], 'ptClear.exe')) \
        :
            print_err('ERROR: Building Photivo failed.')
            return False

        # Move fresh binaries to bin dir
        try:
            shutil.move(os.path.join(self._paths[BUILDDIR][arch], 'photivo.exe'), self._paths[BINDIR][arch])
            shutil.copy(os.path.join(self._paths[BUILDDIR][arch], 'ptClear.exe'), self._paths[BINDIR][arch])
        except OSError as err:
            print_err('ERROR: Copying binaries to "%s" failed.'%self._paths[BINDIR])
            print_err(str(err))
            return False

        return True

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def package(self, arch):
        """Copy data files and DLLs to create a complete Photivo program folder.
        Then create the installer package from that.
        <return>  bool  True if the installer was successfully created, False otherwise
        """
        if not self._copy_data_dlls(arch): return False
        if not self._create_installers(arch): return False
        return True

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def _copy_data_dlls(self, arch):
        """update libs and data files in bin dir
        """
        print_ok('Packaging files (%s)...'%(ArchNames.names[arch]))

        # Changelog: make sure it is up to date (i.e. edited today)
        while True:
            chlog_moddate = datetime.fromtimestamp(os.path.getmtime(self._paths[CHLOGFILE])).date()
            if chlog_moddate >= datetime.today().date():
                break
            else:
                print_warn('Changelog not edited today, but on ' + str(chlog_moddate) + '. It is probably outdated.')
                print('Note that any changes you make after this point will probably not be present')
                print('in the installers.')

                cont = wait_for_key('(R)etry, (c)ontinue or (a)bort?', ['r', 'c', 'a'])
                if cont == 'r':
                    continue
                elif cont == 'c':
                    break
                elif cont == 'a':
                    raise KeyboardInterrupt

        shutil.copy(self._paths[CHLOGFILE], self._paths[BINDIR][arch])

        # copy licence files
        shutil.copy(self._paths[LICFILE], os.path.join(self._paths[BINDIR][arch], 'License.txt'))
        shutil.copy(self._paths[LIC3FILE], os.path.join(self._paths[BINDIR][arch], 'License 3rd party.txt'))

        # Call util scripts to updata data files and DLLs
        if not ptupdata.main([self._paths[PTBASEDIR], self._paths[BINDIR][arch]]):
            return False
        try:
            if not ptuplibs.main([os.environ['TC_BASE'], self._paths[BINDIR][arch], ArchNames.names[arch]]):
                return False
        except KeyError:
            print_err('Environment variable TC_BASE not set.')
            return False

        # strip unnecessary symbols from binaries
        for files in ['*.exe', '*.dll']:
            if not run_cmd([CMD[STRIP], os.path.join(self._paths[BINDIR][arch], files)]):
                print_warn('WARNING: Failed to strip ' + os.path.join(self._paths[BINDIR][arch], files))

        return True


    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def _create_installers(self, arch):
        print_ok('Creating installer (%s) ...'%(ArchNames.names[arch]))

        ptversion = get_cmd_output([CMD[HG], 'log', '-b', self._hgbranch, '-l', '1', '--style', self._paths[VERSTYFILE]])

        with open(self._paths[ISSFILE][arch]) as issfile:
            iss_script = issfile.readlines()

        i = 0
        while i < len(iss_script):
            line = iss_script[i].replace('{{versionstring}}', ptversion)
            line = line.replace('{{changelogfile}}', self._paths[CHLOGFILE])
            line = line.replace('{{outputbasename}}', self._INST_NAME_PATTERN%(self._release_date, ArchNames.names[arch]))
            iss_script[i] = line.replace('{{bindir}}', self._paths[BINDIR][arch])
            i += 1

        iscc_proc = Popen([CMD[ISCC], '/O' + self._paths[PKGBASEDIR], '-'], stdin=PIPE)
        iscc_proc.communicate(input=bytes('\n'.join(iss_script), 'latin_1'))

        if iscc_proc.returncode != 0:
            print_err('ERROR: Creating installer (%s) failed.'%(ArchNames.names[arch]))
            return False

        return True

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def show_summary(self):
        print('\n' + DIVIDER + '\nFinal status\n' + DIVIDER)

        print('The packages are located in:\n' + self._paths[PKGBASEDIR])

        print('\nPhotivo installer 64bit: ', end='')
        inst64_ok = print_file_status(self._install_files[Arch.win64])

        print('Photivo installer 32bit: ', end='')
        inst32_ok = print_file_status(self._install_files[Arch.win32])

        print('\nChangeset info:')
        run_cmd([CMD[HG], 'log', '-b', self._hgbranch, '-l', '1'])

        print(DIVIDER)

        return inst64_ok and inst32_ok


# -----------------------------------------------------------------------
if __name__ == '__main__':
    try:
        sys.exit(0 if main() else 1)
    except KeyboardInterrupt:
        print_err('\nAborted by the user.')
        sys.exit(1)
