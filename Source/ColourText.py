import sys
import re

format_codes = {
    "black": "\u001b[30m",
    "red": "\u001b[31m",
    "green": "\u001b[32m",
    "yellow": "\u001b[33m",
    "blue": "\u001b[34m",
    "magenta": "\u001b[35m",
    "cyan": "\u001b[36m",
    "white": "\u001b[37m",

    "bright black": "\u001b[30;1m",
    "bright red": "\u001b[31;1m",
    "bright green": "\u001b[32;1m",
    "bright yellow": "\u001b[33;1m",
    "bright blue": "\u001b[34;1m",
    "bright magenta": "\u001b[35;1m",
    "bright cyan": "\u001b[36;1m",
    "bright white": "\u001b[37;1m",

    "background Black": "\u001b[40m",
    "background Red":   "\u001b[41m",
    "background Green": "\u001b[42m",
    "background Yellow":   "\u001b[43m",
    "background Blue":  "\u001b[44m",
    "background Magenta":   "\u001b[45m",
    "background Cyan":  "\u001b[46m",
    "background White": "\u001b[47m",

    "bright background Black": "\u001b[40;1m",
    "bright background Red":   "\u001b[41;1m",
    "bright background Green": "\u001b[42;1m",
    "bright background Yellow":   "\u001b[43;1m",
    "bright background Blue":  "\u001b[44;1m",
    "bright background Magenta":   "\u001b[45;1m",
    "bright background Cyan":  "\u001b[46;1m",
    "bright background White": "\u001b[47;1m",

    "bold":   "\u001b[1m",
    "italic":   "\u001b[3m",
    "italics":   "\u001b[3m",
    "underline":  "\u001b[4m",
    "reversed": "\u001b[7m",
    "crossed": "\u001b[9m",

    "reset": "\u001b[0m"
}


def format_text(line="", colour_code=0):
    pattern = '|'.join(rf"\[{code}\]" for code in format_codes)
    line = re.sub(pattern, lambda match: format_codes[match.group()[1:-1]], line)

    line = re.sub(r"\[_text256\]", u"\u001b[38;5;" + str(colour_code) + "m", line)

    line = re.sub(r"\[_background256\]", u"\u001b[48;5;" + str(colour_code) + "m", line)

    matches = re.findall(r"\[_text256_(\d+)_\]", line)
    for match in matches:
        line = re.sub(rf"\[_text256_{match}_\]", u"\u001b[38;5;" + match + "m", line)

    matches = re.findall(r"\[_background256_(\d+)_\]", line)
    for match in matches:
        line = re.sub(rf"\[_background256_{match}_\]", u"\u001b[48;5;" + match + "m", line)

    return line


def show_256TextColour():
    for i in range(0, 16):
        for j in range(0, 16):
            code = str(i * 16 + j)
            sys.stdout.write(u"\u001b[38;5;" + code + "m " + code.ljust(4))
        print(u"\u001b[0m")


def show_256BackgroundColour():
    for i in range(0, 16):
        for j in range(0, 16):
            code = str(i * 16 + j)
            sys.stdout.write(u"\u001b[48;5;" + code + "m " + code.ljust(4))
        print(u"\u001b[0m")


def main():
    from os import system
    from time import sleep
    from random import randint

    system("")

    show_256TextColour()
    print()
    show_256BackgroundColour()
    print()

    while True:
        random_color = randint(0, 255)
        print("", end=format_text("\r[_text256][underline][italic]All[reset][_text256][underline] the colours[reset] "
                                  "[_background256][bold]you want![reset]", random_color))
        sleep(0.2)


if __name__ == "__main__":
    main()
