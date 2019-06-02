import pandas as pd
import numpy as np 
import string
import re
import nltk
from nltk.tokenize import TweetTokenizer
from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer
from dataprep.text_cleaning import *

class TextPrep:
    def __init__(self):
        self.tokenizer = TweetTokenizer()
        self.stemmer = SnowballStemmer('english')
        self.stopwords = set(stopwords.words("english"))

    def tokenize(self, text):
        tknzr = self.tokenizer
        return tknzr.tokenize(text)

    def clean_toks(self, text, rmStop, stem, mpContract):
        '''
        Function to handle text cleaning at the token level
        - Remove stop words
        - Map contractions
        - Stem using Snowball Stemmer
        '''
        toks = self.tokenize(text)
        cl_toks = []
        for t in toks:
            if rmStop == True:
                if len(t) > 3 and t not in self.stopwords:
                    if mpContract == True:
                        if t in CONTRACTION_MAP:
                            t = CONTRACTION_MAP[t]
                        if stem == True:
                            t = self.stemmer.stem(t)
                    cl_toks.append(t)
            else:
                if mpContract == True:
                    if t in CONTRACTION_MAP:
                        t = CONTRACTION_MAP[t]
                    if stem == True:
                        t = self.stemmer.stem(t)
                cl_toks.append(t)
        return ' '.join(cl_toks)               

    def rm_whitespace(self, text):        
        for space in SPACES:
            text = text.replace(space, ' ')
        text = text.strip()
        text = re.sub('\s+', ' ', text)
        return text

    def rm_punct(self, text):
        for p in PUNCT:
            text = text.replace(p, ' ')     
        return text

    def map_punct(self, text):
        for p in PUNCT_MAP:
            text = text.replace(p, PUNCT_MAP[p])    
        return self.rm_punct(text)
    
    def lower_str(self, text):
        return text.lower()
    
    def clean_special_chars(self, text):
        for s in APOSTROPHES: 
            text = text.replace(s, "'")
        for s in SPECIAL_CHARS:
            text = text.replace(s, SPECIAL_CHARS[s])
        return text

    def correct_spelling(self, text):
        for word in SPELL_CORRECT:
            text = text.replace(word, SPELL_CORRECT[word])
        return text

    def clean(self, text, rmCaps, mapPunct, 
                    clSpecial, spCheck, rmStop, stem, mpContract):
        '''
        1. Remove Caps
        2. Map and Remove Punctuation
        3. Clean Special Characters
        4. Correct Spelling Errors
        5. Clean Tokens: Remove Stopwords, Map Contractions, Stem
        6. Remove Whitespace
        '''
        if rmCaps == True:
            text = self.lower_str(text)
        if mapPunct == True:
            text = self.map_punct(text)
        if clSpecial == True:
            text = self.clean_special_chars(text)
        if spCheck == True:
            text = self.correct_spelling(text)

        text = self.clean_toks(text, rmStop, stem, mpContract)
        text = self.rm_whitespace(text)
        
        return text

def test(texts):
    tp = TextPrep()
    print('STOPWORDS: ', tp.stopwords)
    for t in texts:
        print(t)
        print(tp.clean(t, True, False, False, False, False, False, False))
        print(tp.clean(t, False, True, False, False, False, False, False))
        print(tp.clean(t, False, False, True, False, False, False, False))
        print(tp.clean(t, False, False, False, True, False, False, False))
        print(tp.clean(t, False, False, False, False, True, False, False))
        print(tp.clean(t, False, False, False, False, False, True, False))
        print(tp.clean(t, False, False, False, False, False, False, True))
        print(tp.clean(t, False, False, False, False, True, True, False))
        print(tp.clean(t, False, False, False, False, False, True, True))
        print(tp.clean(t, False, False, False, False, True, False, True))
        print(tp.clean(t, True, True, True, True, True, True, True))
        print()
        print('=========================================')
        print()
        
