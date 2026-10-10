"""Extracts a unique set of sensitive words based on the selected fields.

    Iterates through a nested dictionary of categories and attributes, filtering
    by the attributes present in the 'campos' list and accumulating their respective
    words into a set to avoid duplicates.

    Args:
        d (dict): Nested dictionary in the format 
                  {category: {attribute: [word_list]}}.
        campos (list): List of strings with the names of the attributes to filter 
                       (e.g., ["name", "address"]).

    Returns:
        set: A set containing all unique words found in the corresponding attributes.
    """
def createSet(d, campos):
    s = set()
    for categoria, subdict in d.items():
        for atributo, palavras_lista in subdict.items():
            if atributo in campos:
                for palavra in palavras_lista:
                    s.add(palavra)
    return s
