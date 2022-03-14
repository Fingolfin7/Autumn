# noinspection PyShadowingNames
def args(*args):
    print(args)
    ls = args[len(args) - 1]
    print(ls)


args(1, 2, 3, ['hi', 5])

