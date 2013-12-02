#-*- coding: utf8 -*-

import glob, os, shutil, sys
from utils import print_ok, print_warn, print_err

USER_INVOKED = False
QT_UNIVERSAL_PATH = '_universal'

FILE_LIST = {
    'win32': {
        'mingw': [
            'libgcc_s_sjlj-1.dll',
            'libgomp-1.dll',
            'libstdc++-6.dll',
            'libwinpthread-1.dll'
        ],

        'qt': [
            'libEGL.dll',
            'libGLESv2.dll',
            'Qt5Core.dll' + QT_UNIVERSAL_PATH,
            'Qt5Gui.dll',
            'Qt5Network.dll',
            'Qt5Widgets.dll',
            'plugins\\accessible\\qtaccessiblewidgets.dll',
            'plugins\\imageformats\\qgif.dll',
            'plugins\\imageformats\\qico.dll',
            'plugins\\imageformats\\qjpeg.dll',
            'plugins\\imageformats\\qmng.dll',
            'plugins\\imageformats\\qtga.dll',
            'plugins\\imageformats\\qtiff.dll',
            'plugins\\imageformats\\qwbmp.dll',
            'plugins\\platforms\\qwindows.dll'
        ],

        'dev': [
            'intl.dll',
            'libexiv2.dll',
            'libexpat-1.dll',
            'libfftw3-3.dll',
            'libglib-2.0-0.dll',
            'libGraphicsMagick++-3.dll',
            'libGraphicsMagick-3.dll',
            'libGraphicsMagickWand-2.dll',
            'libiconv-2.dll',
            'libjpeg-8.dll',
            'liblcms2-2.dll',
            'liblensfun.dll',
            'liblqr-1-0.dll',
            'libpng15-15.dll',
            'libtiff-5.dll',
            'libtiffxx-5.dll',
            'zlib1.dll'
        ]
    },

    'win64': {
        'mingw': [
            'libgcc_s_seh-1.dll',
            'libgomp-1.dll',
            'libstdc++-6.dll',
            'libwinpthread-1.dll'
        ],

        'qt': [
            'libEGL.dll',
            'libGLESv2.dll',
            'Qt5Core.dll' + QT_UNIVERSAL_PATH,
            'Qt5Gui.dll',
            'Qt5Network.dll',
            'Qt5Widgets.dll',
            'plugins\\accessible\\qtaccessiblewidgets.dll',
            'plugins\\imageformats\\qgif.dll',
            'plugins\\imageformats\\qico.dll',
            'plugins\\imageformats\\qjpeg.dll',
            'plugins\\imageformats\\qmng.dll',
            'plugins\\imageformats\\qtga.dll',
            'plugins\\imageformats\\qtiff.dll',
            'plugins\\imageformats\\qwbmp.dll',
            'plugins\\platforms\\qwindows.dll'
        ],

        'dev': [
            'libexiv2.dll',
            'libexpat-1.dll',
            'libfftw3-3.dll',
            'libglib-2.0-0.dll',
            'libGraphicsMagick++-3.dll',
            'libGraphicsMagick-3.dll',
            'libGraphicsMagickWand-2.dll',
            'libiconv-2.dll',
            'libintl-8.dll',
            'libjpeg-8.dll',
            'liblcms2-2.dll',
            'liblensfun.dll',
            'liblqr-1-0.dll',
            'libpng15.dll',
            'libtiff-5.dll',
            'libtiffxx-5.dll',
            'zlib1.dll'
        ]
    }
}

# -----------------------------------------------------------------------
def main(cli_params):
    if len(cli_params) == 0:
        print_err('Not implemented yet.')
        return False
    elif len(cli_params) == 3:
        srcdir  = os.path.abspath(cli_params[0])
        destdir = os.path.abspath(cli_params[1])
        arch    = cli_params[2]
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

    if not arch in ['win32', 'win64']:
        print_err('ERROR: Unknow architecture. Must be "win32" or "win64".')
        return False

    if not kill_old_libs(destdir):
        return False

    src_mingw = os.path.join(srcdir, 'mingw', 'current', 'bin')
    src_qt    = os.path.join(srcdir, 'dev', 'current', 'qt', 'bin')
    src_dev   = os.path.join(srcdir, 'dev', 'current', 'bin')
    file_dict = FILE_LIST[arch]

    file_list = []
    for file in file_dict['mingw']:
        file_list.append([os.path.join(src_mingw, file), destdir])

    for file in file_dict['qt']:
        if file.endswith(QT_UNIVERSAL_PATH):
            destfile = file.replace(QT_UNIVERSAL_PATH, '')
        else:
            destfile = file

        if '\\' in file:
            file_list.append([os.path.join(os.path.dirname(src_qt), file),
                              os.path.join(destdir, destfile)])
            os.makedirs(os.path.dirname(os.path.join(destdir, destfile)), exist_ok=True)
        else:
            file_list.append([os.path.join(src_qt, file),
                              os.path.join(destdir, destfile)])

    for file in file_dict['dev']:
        file_list.append([os.path.join(src_dev, file), destdir])

    if not copy_libs(file_list):
        return False

    print_ok('Libraries successfully updated.')
    return True


# -----------------------------------------------------------------------
def copy_libs(file_list):
    status = True

    for entry in file_list:
        srcfile, dest = entry
        try:
            print(os.path.split(srcfile)[1])
            shutil.copy(srcfile, dest)
        except OSError as err:
            print_err(str(err))
            print_err('Source: ' + srcfile)
            print_err('Dest  : ' + dest)
            status = False

    return status


# -----------------------------------------------------------------------
def kill_old_libs(destdir):
    status = True

    for file in glob.glob(os.path.join(destdir, '*.dll')):
        try:
            os.remove(file)
        except OSError as err:
            print_err('Could not delete ' + file)
            print_err(str(err))
            status = False

    return status


# -----------------------------------------------------------------------
if __name__ == '__main__':
    try:
        USER_INVOKED = True
        sys.exit(0 if main(sys.argv[1:]) else 1)
    except KeyboardInterrupt:
        print_err('\nAborted by the user.')
        sys.exit(1)
