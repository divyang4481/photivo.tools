#-*- coding: utf8 -*-

import os, shutil, sys
from utils import print_ok, print_warn, print_err

USER_INVOKED = False

DIR_LIST = [
    # dir name          # files to ignoe
    ['ChannelMixers',   None],
    ['Curves',          None],
    ['LensfunDatabase', None],
    ['Presets',         None],
    ['Profiles',        None],
    ['Themes',          None],
    ['Translations',    '*.ts'],
    ['UISettings',      None]
]

# -----------------------------------------------------------------------
def main(cli_params):
    if len(cli_params) == 0:
        print_err('Not implemented yet.')
        return False
    elif len(cli_params) == 2:
        srcdir  = os.path.abspath(cli_params[0])
        destdir = os.path.abspath(cli_params[1])
    else:
        print_err('Wrong number of arguments. Must be none or two.')
        return False

    if not os.path.isdir(srcdir):
        print_err('ERROR: Source base directory "%s" missing.'%srcdir)
        return False

    os.makedirs(destdir, exist_ok=True)
    if not os.path.isdir(destdir):
        print_err('ERROR: Destination base "%s" is not a directory.'%destdir)
        return False

    for direntry in DIR_LIST:
        try:
            dest_subdir = os.path.join(destdir, direntry[0])
            if os.path.exists(dest_subdir):
                shutil.rmtree(dest_subdir)
        except Exception as err:
            print_err('ERROR removing existing destination: ' + direntry[0])
            print_err(str(err))
            return False

    for direntry in DIR_LIST:
        print('Updating:', direntry[0])

        try:
            if direntry[1] == None:
                ignorer = None
            else:
                ignorer = shutil.ignore_patterns(direntry[1])

            shutil.copytree(os.path.join(srcdir, direntry[0]),
                            os.path.join(destdir, direntry[0]),
                            ignore=ignorer)
        except Exception as err:
            print_err('ERROR copying data directory: ' + direntry[0])
            print_err(str(err))
            return False

    print_ok('Data files successfully updated.')
    return True


# -----------------------------------------------------------------------
if __name__ == '__main__':
    try:
        USER_INVOKED = True
        sys.exit(0 if main(sys.argv[1:]) else 1)
    except KeyboardInterrupt:
        print_err('\nAborted by the user.')
        sys.exit(1)
