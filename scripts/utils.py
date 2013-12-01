#-*- coding: utf8 -*-

# -----------------------------------------------------------------------
# Try to setup coloured text output for the Windows console.
# When something goes wrong fall back to dummies without colour.
try:
    from ctypes import windll, Structure, c_short, c_ushort, byref

    class COORD(Structure): _fields_ = [('X', c_short), ('Y', c_short)]
    class SMALL_RECT(Structure): _fields_ = [('Left', c_short), ('Top', c_short), ('Right', c_short), ('Bottom', c_short)]
    class CONSOLE_SCREEN_BUFFER_INFO(Structure):
        _fields_ = [('dwSize', COORD),
                    ('dwCursorPosition', COORD),
                    ('wAttributes', c_ushort),
                    ('srWindow', SMALL_RECT),
                    ('dwMaximumWindowSize', COORD)]
    stdout_handle = windll.kernel32.GetStdHandle(-11)

    # get current console setup
    csb_info = CONSOLE_SCREEN_BUFFER_INFO()
    windll.kernel32.GetConsoleScreenBufferInfo(stdout_handle, byref(csb_info))

    DEFAULT_COLORS = csb_info.wAttributes
    GREEN          = 0x0002
    YELLOW         = 0x0006
    BRIGHT_RED     = 0x0004 | 0x0008

    def print_color(color, msg):
        windll.kernel32.SetConsoleTextAttribute(stdout_handle, color | DEFAULT_COLORS)
        print(msg)
        windll.kernel32.SetConsoleTextAttribute(stdout_handle, DEFAULT_COLORS)
    def reset_color():
        windll.kernel32.SetConsoleTextAttribute(stdout_handle, DEFAULT_COLORS)
        sys.stdout.flush()
except:
    GREEN = YELLOW = BRIGHT_RED = 0
    def print_color(color, msg):
        print(msg)
    def reset_color():
        pass

def print_ok(msg):
    print_color(GREEN, msg)

def print_warn(msg):
    print_color(YELLOW, msg)

def print_err(msg):
    print_color(BRIGHT_RED, msg)


