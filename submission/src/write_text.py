import string

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

Doc= "Ana, Correia."
W = {"Ana":[1]}

def FinalText(Document, WordsSet):
    """Substitui ocorrências específicas de palavras num documento por asteriscos (*),
    ignorando pontuações e vírgulas na contagem dos índices e na correspondência.

    Args:
        Document (str): O texto completo do documento a ser processado.
        WordsSet (dict): Dicionário com as palavras e os seus índices válidos.

    Returns:
        str: O texto modificado com as palavras correspondentes substituídas por '*'.
    """
    
    DocSplit = Document.split()
    resultado = []
    i = 1

    for token in DocSplit:
        # Remove pontuações das bordas da palavra (ex: "casa," -> "casa")
        clean_word = token.strip(string.punctuation)
        
        # Se o token for apenas uma pontuação isolada (ex: ",")
        if not clean_word:
            resultado.append(token)
            continue

        # Verifica se a palavra limpa está no dicionário e se o índice coincide
        if clean_word in WordsSet and i in WordsSet[clean_word]:
            # Substitui a palavra por '*' mantendo a pontuação original (se houver)
            replaced_token = token.replace(clean_word, "*", 1)
            resultado.append(replaced_token)
        else:
            resultado.append(token)
        
        # Incrementa o índice apenas quando processamos uma palavra real
        i += 1
            
    return " ".join(resultado)

print(FinalText(Doc, W))