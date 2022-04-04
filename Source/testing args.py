from Autumn import commands
from projects import Projects
import sys
import gc


# got this from https://towardsdatascience.com/the-strange-size-of-python-objects-in-memory-ce87bdfbb97f
def actual_size(input_obj):
    memory_size = 0
    ids = set()
    objects = [input_obj]
    while objects:
        new = []
        for obj in objects:
            if id(obj) not in ids:
                ids.add(id(obj))
                memory_size += sys.getsizeof(obj)
                new.append(obj)
        objects = gc.get_referents(*new)
    return memory_size


obj = Projects()
print(actual_size(obj))

