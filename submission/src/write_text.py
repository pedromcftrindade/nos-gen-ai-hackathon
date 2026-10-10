"""
    Creates a flat dictionary from a nested dictionary, filtering by specific attributes.

    Args:
        d (dict): Nested dictionary in the format {category: {attribute: {name: t, ...}, ...}, ...}.
        fields (iterable): Collection (such as a list or set) containing the names of the attributes to filter.

    Returns:
        dict: A new flat dictionary containing the {name: t} pairs whose attributes belong to `fields`.
"""
def createDict(d, fields):
    newDict = {}
    for categoria, subdict in d.items():
        for atributo, list_words in subdict.items():
            if atributo in fields:
                for name, t in list_words.items():
                    newDict[name] = t
    return newDict

"""
    Replaces specific word occurrences in a document with asterisks (*),
    based on a dictionary of words and positions (1-based indices).

    Args:
        Document (str): The full text of the document to be processed.
        WordsSet (dict): Dictionary where the key is the word and the value is a set/list 
                         of positions (e.g., {word: {1, 4, 12}}) where the replacement should occur.

    Returns:
        str: The modified text with the corresponding words replaced by '*'.
    """
def FinalText(Document, WordsSet):
    DocSplit = Document.split()
    resultado = []
    i=1

    for word in DocSplit:
        if word in WordsSet and i in WordsSet[word]:
            resultado.append("*")
        else:
            resultado.append(word)
        i += 1
            
    # Junta todos os elementos da lista numa única string, separados por espaços
    return " ".join(resultado)

