# noinspection PyShadowingNames
def args(*args):
    print(args)
    ls = args[len(args) - 1]
    print(ls)


args(1, 2, 3, ['hi', 5])

try:
    period = int("6 hello_world")
except ValueError:
    print("not an int")
