import jsonlines
import spacy
from word2number import word_to_num
import numpy as np
import re
from tqdm.autonotebook import tqdm
from pathlib import Path
import typer

#if __name__ == "__main__"
#nlp = spacy.load("en_core_web_lg")

_num_words = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
              'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen',
              'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty',
              'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety',
              'hundred', 'thousand', 'million', 'billion', 'trillion', 'quadrillion',
              'gajillion', 'bazillion', 'dozen', 'dozens', 'hundreds', 'thousands']

def like_num(text):
    text = text.replace(',', '').replace('.', '')
    if text.isdigit():
        return True
    if text.count('/') == 1:
        num, denom = text.split('/')
        if num.isdigit() and denom.isdigit():
            return True
    if text in _num_words:
        return True
    return False

def cand_generator(doc):
    for i in doc:
        if like_num(i.text):
            if any([like_num(j.text) for j in i.ancestors]):
                continue
            phrase = [i] + [j for j in i.children if j.dep_ in ['amod', 'quantmod', 'compound', 'advmod']]
            phrase.sort(key=lambda x: x.i)
            yield(phrase)
            
def cand_text(doc):
    spans = [i for i in cand_generator(doc)]
    text_list = []
    for s in spans:
        text = ''.join([i.text_with_ws for i in s if like_num(i.text)]).strip()
        text_list.append(text)
    return text_list

def oom_match(doc, size_cat, normalize=True, debug=False):
    # get spacy spans for number phrases
    cands_raw = list(cand_generator(doc))
    # ...and also in text form, stripping out non-number words
    cands_text = cand_text(doc)
    # convert number words to numeric value
    nums = []
    for i in cands_text:
        try:
            nn = word_to_num(i) 
        except ValueError:
            # this is caused by some weird dates ("4/22")
            # for now, assign a too-large number to exclude it
            nn = 1000000000
        nums.append(nn)
    if debug:
        print(cands_raw)
    # convert to CCC size_cat scale
    oom = [len(str(int(i)))-1 for i in nums]
    # check if the extracted span is the right size_cat
    oom_locs = [int(i == int(size_cat)) for i in oom]
    
    # initialize a vector of zeros
    word_labels = np.zeros(len(doc))
    # find the spans that are an oom match, and assign 1 to their tokens
    for n, loc in enumerate(oom_locs):
        if loc:
            poses = [i.i for i in cands_raw[n]]
            if normalize:
                weight = 1 / sum(oom_locs)
            else:
                weight = 1
            word_labels[poses] = weight
            
    return word_labels

def keyword_match(doc, weight=1):

    search_terms = ["protesters", "demonstrators", "gathered", "crowd", "rallied", "attended",
               "picketed", "protest"]

    # check each sentence to see if it has a keyword
    keyword_match = []
    for c in cand_generator(doc):
        matches = [bool(re.search(s, c[0].sent.text)) for s in search_terms]
        if sum(matches) > 0:
            keyword_match.append([i.i for i in c])
            
    # initialize a vector of zeros
    word_labels = np.zeros(len(doc))
    # assign 1 to the spans that are in a keyword sentence
    for i in keyword_match:
        word_labels[i] = weight
        
    return word_labels

def label_doc(doc, ex, qa=None):
    #qa_labels = qa_match(doc, qa)
    oom_labels = oom_match(doc, ex['size_cat'])
    keyword_labels = keyword_match(doc)
    all_labels = np.array([#qa_labels, 
                            keyword_labels, 
                            oom_labels])
    votes = np.sum(all_labels, axis=0)
    votes2 = np.multiply(votes, oom_labels) # remove ones that are the wrong oom.
    maj_vote = votes2 == np.max(votes2)
    
    voted_words = [i for n, i in enumerate(doc) if maj_vote[n]]
    start_char = voted_words[0].idx
    # Get the last word from the first contiguous span
    for n, current_word in enumerate(voted_words):
        prev_word = voted_words[n-1]
        if (n + 1) == len(voted_words):                
            end_word = current_word
            break
        if n == 0:
            continue
        if current_word.i - prev_word.i > 1:
            end_word = prev_word
            break
        if current_word.i == len(doc):
            end_word = current_word
            
    end_char = end_word.idx + len(end_word)
    answer_text = doc.text[start_char:end_char]

    ## get the sentence with the soft labeled answer
    context = end_word.sent
    
    output = {#"token_labels" : maj_vote.tolist(),
        "start_char": start_char,
        "end_char": end_char,
        "context": context.text,
        "labeled_text": answer_text}
    return output

def label_all(docs, train):
    doc_labels = []
    for doc, ex in tqdm(zip(docs, train), total=len(train)):
        doc_labels.append(label_doc(doc, ex))
    return doc_labels
        
def accuracy_eval(data, doc_labels):
    correct = []
    for t, l in zip(data, doc_labels):
        correct.append(t['size_text'].lower() == l['labeled_text'].lower())

    return np.mean(correct)

def main(ccc_file: Path):
    nlp = spacy.load("en_core_web_lg")
    with jsonlines.open(ccc_file, "r") as f:
        data = list(f.iter())

    if 'text' in data[0].keys():
        text_key = 'text'
    else:
        text_key = 'para'
    docs = list(tqdm(nlp.pipe([i[text_key] for i in data]), total=len(data)))
    doc_labels = label_all(docs, data)

    print(accuracy_eval(data, doc_labels))

    with jsonlines.open("soft_labeled.jsonl", "w") as f:
        f.write_all(doc_labels)

if __name__ == "__main__":
    typer.run(main)