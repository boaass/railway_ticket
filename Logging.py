import termcolor


class Logging:
    def __init__(self):
        pass

    flag = True

    @classmethod
    def error(cls, msg):
        if cls.flag:
            print "".join([termcolor.colored("ERROR", "red"), ": ", termcolor.colored(msg, "white")])

    @classmethod
    def warning(cls, msg):
        if cls.flag:
            print "".join([termcolor.colored("WARNING", "yellow"), ": ", termcolor.colored(msg, "white")])

    @classmethod
    def info(cls, msg):
        if cls.flag:
            print "".join([termcolor.colored("INFO", "magenta"), ": ", termcolor.colored(msg, "white")])

    @classmethod
    def debug(cls, msg):
        if cls.flag:
            print "".join([termcolor.colored("DEBUG", "magenta"), ": ", termcolor.colored(msg, "white")])

    @classmethod
    def success(cls, msg):
        if cls.flag:
            print "".join([termcolor.colored("SUCCESS", "green"), ": ", termcolor.colored(msg, "white")])
