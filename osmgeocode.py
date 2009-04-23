#!/usr/bin/python

# Simple OSM Geocoder with correction magic from the always-awesome Peter Norvig:
# http://www.norvig.com/spell-correct.html

# Python OSM library (c) 2007 Brandon Martin-Anderson from the Graphserver project:
# http://github.com/bmander/graphserver/tree/master
from osm import OSM


class Counter(object):
    def __init__(self, smoothing=True):
        self.store = {}
        self.smoothing = smoothing
    
    def inc(self, key):
        if self.store.has_key(key):
            self.store[key] += 1
        else:
            self.store[key] = 1
    
    def inc_all(self, arr):
        for key in arr:
            self.inc(key)
    
    def has(self, key):
        return self.store.has_key(key)
    
    def count(self, key):
        if self.store.has_key(key):
            return self.store[key]
        else:
            if self.smoothing:
                return 1
            else:
                return 0
                
    def __str__(self):
        out = []
        for key in self.store.keys():
            out.append(key + '=' + str(self.store[key]))
        return '<Counter{' + ', '.join(out) + '}>'



class Geocoder(object):
    def __init__(self, osm):
        self.osm = osm
        self.extract_from_graph()
    
    def compact(self, s):
        s_lower = s.lower()
        out = []
        for c in s_lower:
            if c.isspace() and len(out) > 0 and out[-1] != ' ':
                out.append(c)
            elif c.isalpha() or c.isdigit():
                out.append(c)
        if len(out) > 0 and out[-1].isspace():
            del out[-1]
        return self.expand_abbrev(''.join(out))
    
    def expand_abbrev(self, w):
        abbrevs = {
            'rd': 'road',
            'av': 'avenue',
            'ave': 'avenue',
            'st': 'street',
            'cls': 'close'
        }
        out = []
        for word in w.split():
            if word in abbrevs:
                out.append(abbrevs[word])
            else:
                out.append(word)
        return ' '.join(out)
            
    def extract_from_graph(self):
        self.places = {}
        self.word_freqs = Counter()
        for way_id in self.osm.ways:
            way = self.osm.ways[way_id]
            if way.tags.has_key('name'):
                compact_name = self.compact(way.tags['name'])
                self.places[compact_name] = way_id
                self.word_freqs.inc_all(compact_name.split())
    
    def edits1(self, word):
        alphabet = 'abcdefghijklmnopqrstuvwxyz'
        n = len(word)
        return set(
            # deletion: 'anana', 'bnana', 'baana', 'banna', 'banaa', 'banan'
            [word[0:i]+word[i+1:] for i in xrange(n)] +
            # transposition: 'abnana', 'bnaana', 'baanna', 'bannaa', 'banaan'
            [word[0:i]+word[i+1]+word[i]+word[i+2:] for i in xrange(n-1)] +
            # alteration: 'aanana', 'banana', 'canana', 'danana', ..., 'bananz'
            [word[0:i]+c+word[i+1:] for i in xrange(n) for c in alphabet] +
            # insertion: 'abanana', 'bbanana', 'cbanana', 'dbanana', ..., 'bananaz'
            [word[0:i]+c+word[i:] for i in xrange(n+1) for c in alphabet]
        )
    
    def edits2(self, word):
        return set(e2 for e1 in self.edits1(word) for e2 in self.edits1(e1) if self.word_freqs.has(e2))
    
    def known(self, words):
        return set(w for w in words if self.word_freqs.has(w))
    
    def correct(self, word):
        candidates = self.known([word]) or self.known(self.edits1(word)) or self.known(self.edits2(word)) or [word]
        return max(candidates, key=lambda w: self.word_freqs.count(w))
    
    
    def lookup(self, placename, fuzzy=True):
        pname = self.compact(placename)
        if self.places.has_key(pname):
            return (pname, self.places[pname])
        elif fuzzy:
            c_name = ' '.join([self.correct(w) for w in pname.split()])
            return self.lookup(c_name, False)
        return (pname, None)
    
    def lookup_partial(self, placename):
        pname = set(self.compact(placename).split())
        candidate = None
        candidate_score = 0
        for place in self.places:
            score = len(pname & set(place.split()))
            if score > candidate_score:
                candidate = place
                candidate_score = score
        if candidate:
            return (candidate, self.places[candidate])
        return (placename, None)
    
    def resolve(self, placename):
        (lookup_name, way_id) = self.lookup(placename)
        if way_id:
            return (lookup_name, self.osm.ways[way_id])
        else:
            (lookup_name, way_id) = self.lookup_partial(lookup_name)
            if way_id:
                return (lookup_name, self.osm.ways[way_id])
        return (lookup_name, None)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print "usage: %s <placename>" % sys.argv[0]
        raise SystemExit
    
    placename = ' '.join(sys.argv[1:])
    
    map_file = 'sample.osm'
    coder = Geocoder(OSM(map_file))
        
    (placename, way) = coder.resolve(placename)
    if way:
        print way.tags['name'] + ':', way.get_projected_points()[0]
    else:
        print "Placename not found:", placename