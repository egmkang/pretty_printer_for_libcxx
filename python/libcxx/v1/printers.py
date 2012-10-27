import gdb
import itertools
import re
import io

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
        return ('"%s"' % (self.ptr.string (length = self.length)))

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

class CxxListPrinter:
    "std::__1::list"

    class _iterator:
        def __init__(self, begin, size):
            self.begin = begin
            self.count = 0
            self.size = size

        def __iter__(self):
            return self
        
        def next(self):
            count = self.count
            self.count = self.count + 1
            if count == self.size:
                raise StopIteration
            value = self.begin.dereference()['__value_']
            self.begin = self.begin['__next_']
            return ('[%d]' % count, value)

    def __init__(self, typename, val):
        self.val = val
        self.typename = typename

    def children(self):
        return self._iterator(self.val['__end_']['__next_'],
                              self.val['__size_alloc_']['__first_'])

    def to_string(self):
        size = self.val['__size_alloc_']['__first_']
        return ('%s of length %d' % (self.typename, size))

    def display_hint(self):
        return 'std::list'

class CxxDequePrinter:
    "std::__1::deque"

    class _iterator:
        def __init__(self, begin, offset, block, size):
            self.begin = begin
            self.count = 0
            self.size = size
            self.offset = offset
            self.block = block

        def __iter__(self):
            return self
        
        def next(self):
            count = self.count
            self.count = self.count + 1
            if count == self.size:
                raise StopIteration
            index = count + self.offset
            i,j = index / self.block, index % self.block
            value = ((self.begin + i).dereference() + j).dereference()
            return ('[%d]' % count, value)

    def __init__(self, typename, val):
        self.val = val
        self.typename = typename

    def children(self):
        begin = self.val['__map_']['__first_']
        block = self.val['__block_size']
        offset = self.val['__start_']
        size  = self.val['__size_']['__first_']

        return self._iterator(begin, offset, block, size)
                              

    def to_string(self):
        size = self.val['__size_']['__first_']
        return ('%s of length %d' % (self.typename, size))

    def display_hint(self):
        return 'std::deque'

class CxxRbTreeIterator:
    "RbTreeIterator"
    def __init__(self, nodetype, begin, size, fmt):
        self.begin = begin
        self.count = 0
        self.size = size
        self.nodetype = nodetype
        self.fmt = fmt

    def __iter__(self):
        return self
    def get_min_node(self, node):
        """
        _NodePtr                           
        __tree_min(_NodePtr __x) _NOEXCEPT 
        {                                  
           while (__x->__left_ != nullptr) 
                __x = __x->__left_;        
           return __x;                     
        }                                  
        """
        while node['__left_'] != 0:
            node = node['__left_']
        return node

    def get_next_node(self, node):
        """
        _NodePtr
        __tree_next(_NodePtr __x) _NOEXCEPT
        {
            if (__x->__right_ != nullptr)
                return __tree_min(__x->__right_);
            while (!__tree_is_left_child(__x))
                __x = __x->__parent_;
            return __x->__parent_;
        }
        """
        begin = node
        if begin['__right_'] != 0:
            return self.get_min_node(begin['__right_'])
        while begin != begin['__parent_']['__left_']:
            begin = begin['__parent_']
        return begin['__parent_']

    def next(self):
        count = self.count
        self.count = self.count + 1
        if count == self.size:
            raise StopIteration
        value_ptr = self.begin.cast(self.nodetype)
        value = value_ptr.dereference()['__value_']
        self.begin = self.get_next_node(self.begin)
        return self.fmt(count, value)

class CxxMapPrinter:
    "std::__1::map and std::multiset"

    def __init__(self, typename, val):
        self.typename = typename
        self.val = val

    def children(self):
        begin = self.val['__tree_']['__begin_node_']
        nodetype = begin.type
        size = self.val['__tree_']['__pair3_']['__first_']
        fmt = lambda count,value : ('[%s]' % value['first'], value['second'])
        return CxxRbTreeIterator(nodetype, begin, size, fmt)

    def to_string(self):
        begin = self.val['__tree_']['__begin_node_']
        keytype = self.val.type.template_argument(0)
        valuetype = self.val.type.template_argument(1)
        size = self.val['__tree_']['__pair3_']['__first_']
        return ('%s of length %d' % (self.typename, size))

    def display_hint(self):
        return 'std::map'

class CxxSetPrinter:
    "std::__1::set and std::__1::multiset"

    def __init__(self, typename, val):
        self.typename = typename
        self.val = val

    def children(self):
        begin = self.val['__tree_']['__begin_node_']
        nodetype = begin.type
        size = self.val['__tree_']['__pair3_']['__first_']
        fmt = lambda count,value : ('[%d]' % count, value)
        return CxxRbTreeIterator(nodetype, begin, size, fmt)

    def to_string(self):
        begin = self.val['__tree_']['__begin_node_']
        keytype = self.val.type.template_argument(0)
        valuetype = self.val.type.template_argument(1)
        size = self.val['__tree_']['__pair3_']['__first_']
        return ('%s of length %d' % (self.typename, size))

    def display_hint(self):
        return 'std::set'

class CxxStackPrinter:
    "std::__1::stack or std::__1::queue"

    def __init__ (self, typename, val):
        self.typename = typename
        self.visualizer = gdb.default_visualizer(val['c'])

    def children (self):
        return self.visualizer.children()

    def to_string (self):
        return '%s wrapping: %s' % (self.typename,
                self.visualizer.to_string())

    def display_hint (self):
        if hasattr (self.visualizer, 'display_hint'):
            return self.visualizer.display_hint ()
        return None


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
    #print("Not Fount Type %s" % (typename))
    return None

def register_libcxx_printers(obj):
    global _type_parse_map
    if len(_type_parse_map) < 1:
        reg_function('^std::__1::basic_string<char.*>$', CxxStringPrinter)
        reg_function('^std::__1::string$', CxxStringPrinter)
        reg_function('^std::__1::vector<.*>$', CxxVectorPrinter)
        reg_function('^std::__1::list<.*>$', CxxListPrinter)
        reg_function('^std::__1::deque<.*>$', CxxDequePrinter)
        reg_function('^std::__1::stack<.*>$', CxxStackPrinter)
        reg_function('^std::__1::priority_queue<.*>$', CxxStackPrinter)
        reg_function('^std::__1::queue<.*>$', CxxStackPrinter)
        reg_function('^std::__1::map<.*>$', CxxMapPrinter)
        reg_function('^std::__1::multimap<.*>$', CxxMapPrinter)
        reg_function('^std::__1::set<.*>$', CxxSetPrinter)
        reg_function('^std::__1::multiset<.*>$', CxxSetPrinter)
    
    if obj is None:
        obj = gdb
    obj.pretty_printers.append(lookup_type)

