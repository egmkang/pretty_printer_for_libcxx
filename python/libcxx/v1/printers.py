import gdb
import itertools
import re

class CxxStringPrinter:
    "Print a std::__1::basic_string"
    def __init__(self, typename, val):
        self.val = val

    def to_string(self):
        self.is_short = self.val['__r_']['__first_']['__s']['__size_'] & 1
        if self.is_short == 0 :
            self.ptr = self.val['__r_']['__first_']['__s']['__data_']
            self.length = self.val['__r_']['__first_']['__s']['__size_'] / 2 % 256
        else:
            self.ptr = self.val['__r_']['__first_']['__l']['__data_']
            self.length = self.val['__r_']['__first_']['__l']['__size_'] + 1
        return self.ptr.string (length = self.length)

    def display_hint (self):
        return "std::string"

class CxxVectorPrinter:
    "std::__1::vector"

    class _iterator:
        def __init__(self, begin, end):
            self.begin = begin
            self.end = end
            self.count = 0

        def __iter__(self):
            return self
        
        def next(self):
            count = self.count
            self.count = self.count + 1
            if self.begin == self.end:
                raise StopIteration
            value = self.begin.dereference()
            self.begin = self.begin + 1
            return ('[%d]' % count, value)

    def __init__(self, typename, val):
        self.val = val
        self.typename = typename

    def children(self):
        return self._iterator(self.val['__begin_'],
                              self.val['__end_'])

    def to_string(self):
        begin = self.val['__begin_']
        end = self.val['__end_'] 
        size = end - begin
        return ('%s of length %d' % (self.typename, int(end - begin)))

    def display_hint(self):
        return 'std::vector'

_type_parse_map = []

def reg_function(regex, parse):
    global _type_parse_map

    p = re.compile(regex)

    _type_parse_map.append((p,parse))

def lookup_type (val):
    global _type_parse_map
    typename = str(val.type)
    for (regex, Printer) in _type_parse_map:
        m = regex.match(typename)
        if m is not None:
            return Printer(typename, val)
    return None

def register_libcxx_printers(obj):
    global _type_parse_map
    if len(_type_parse_map) < 1:
        reg_function('^std::__1::basic_string<char,.*>$', CxxStringPrinter)
        reg_function('^std::__1::string.*$', CxxStringPrinter)
        reg_function('^std::__1::vector<.*>$', CxxVectorPrinter)

    gdb.pretty_printers.append(lookup_type)

