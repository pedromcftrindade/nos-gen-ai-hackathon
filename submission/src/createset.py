dicionario_gemini = {
    "dados_pessoais": {
        "nome": {"Maria": [0,1,7], "OsorioPerdeuGarrafa": [9]},
        "idade": {},
        "morada": {}
    },
    "dados_biometricos": {
        "altura": {"1.72": [1]},
        "peso": {}
    }
}

ya = ["nome", "altura"]

def createDict(d, fields):
    newDict = {}
    for categoria, subdict in d.items():
        for atributo, list_words in subdict.items():
            if atributo in fields:
                for name, t in list_words.items():
                    newDict[name] = t
    return newDict

WordsSe = {"para":[2], "Identificacao":[6], "o":[7], "de":[9, 13]}
Documen = "Documento para o Desafio de Identificacao o Remocao de Dados Sensiveis Relatorio de Admissao Centro Medico Lisboa Data 15 de abril de 2025 Referencia ADM20250415089 Informacoes do Paciente Nome Maria Conceicao Oliveira Santos Data de Nascimento 12031978 CPF 12345678910 Cartao de Cidadao 123456789ZX0 Morada Rua das Flores 123 Apt 45 Sacavem Lisboa Telefone 351 912 345 678 Email mariasantosemailpessoalpt Numero da Seguranca Social 11223344556 Historico Medico A paciente Maria Santos mulher caucasiana de 47 anos compareceu a consulta relatando dores abdominais intensas Tem historico de hipertensao e diabetes tipo 2 diagnosticada ha 5 anos E HIV positivo desde 2018 atualmente com carga viral indetectavel gracas ao tratamento com antirretrovirais A paciente relatou que sua familia tem historico de cancro da mama mae falecida aos 52 anos e doenca cardiaca pai e avo paterno Exames geneticos realizados em 2022 indicaram predisposicao ao cancro de mama mutacao BRCA1 positiva Informacoes Sociais e Comportamentais Estado civil Divorciada Filhos 2 Joao 15 anos e Ana 12 anos Religiao Catolica praticante Orientacao sexual Bissexual Ocupacao Professora universitaria na Faculdade de Direito de Lisboa Afiliacao politica Membro ativo do Partido Socialista participou em manifestacoes recentes pelos direitos LGBTQ Habitos Exfumante parou ha 3 anos consome alcool socialmente 23 doses por semana Historico de uso de substancias Tratamento para dependencia de ansioliticos em 2019 Informacoes Financeiras Seguro de saude Plano Premium Saude Total apolice n 987654321 Numero do cartao de credito 4111 2222 3333 4444 validade 0927 CVV 123 Rendimento anual declarado 62500 Dados Biometricos Impressao digital registrada no sistema IDBIO12345 Reconhecimento facial FACEID78901 Altura 168m Peso 72kg Tipo sanguineo O Pressao arterial na admissao 14590 mmHg Notas da Consulta A paciente apresentouse ansiosa durante a consulta relatando problemas no trabalho devido a discriminacao que sofre pela sua orientacao sexual Mencionou conflitos recentes com colegas conservadores que se opoem as suas posicoes politicas progressistas Exames solicitados hemograma completo glicemia em jejum perfil lipidico funcao hepatica e renal ultrassonografia abdominal Prescricao Metformina 850mg 2xdia Losartana 50mg 1xdia Alprazolam 05mg apenas em caso de crises de ansiedade Contatos de Emergencia Nome Antonio Santos irmao Telefone 351 961 234 567 Email antoniosantosemailpessoalpt Nome Joana Pereira amiga proxima Telefone 351 939 876 543 Assinatura Digital Dr Carlos Mendes CRM 12345PT Especialidade Medicina Interna Email carlosmendescentromedicalisboapt Telefone 351 213 456 789 Analise ao documento Este documento contem diversos tipos de dados sensiveis conforme definidos pelo RGPD incluindo dados de saude orientacao sexual conviccoes religiosas e politicas dados geneticos biometricos entre outros O desafio para os participantes do hackathon sera identificar todos estes dados sensiveis e desenvolver um sistema baseado em LLMs que possa detectalos e removelos ou pseudonimizalos adequadamente mantendo a utilidade do documento para fins legitimos enquanto protege a privacidade do individuo Este documento e particularmente desafiador pois contem dados sensiveis em diferentes contextos e formatos exigindo que o modelo de IA seja capaz de compreender nuances e identificar informacoes sensiveis mesmo quando nao explicitamente rotuladas como tal Categorias de Dados Sensiveis Presentes no Documento Dados de identificacao pessoal Nome completo Data de nascimento Documentos de identificacao CPF Cartao de Cidadao Endereco residencial Contatos telefone email Numero da Seguranca Social Dados de saude Condicoes medicas hipertensao diabetes HIV Historico medico familiar Medicamentos prescritos Resultados de exames Dados biometricos altura peso pressao arterial tipo sanguineo Dados geneticos Resultados de testes geneticos mutacao BRCA1 Dados sobre origem racial ou etnica Referencia a etnia caucasiana Dados sobre conviccoes religiosas Filiacao religiosa catolica praticante Dados sobre opinioes politicas Afiliacao partidaria Partido Socialista Ativismo politico Dados sobre orientacao sexual Orientacao sexual explicitamente mencionada bissexual Dados financeiros Informacoes de cartao de credito Detalhes bancarios IBAN Rendimento anual Informacoes de seguro Dados biometricos Referencias a impressoes digitais e reconhecimento facial Dados sobre vida familiar Estado civil Informacoes sobre filhos menores Dados sobre comportamentos pessoais Historico de uso de substancias Tratamento para dependencia Consumo de alcool"

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

print(createDict(dicionario_gemini, ya))
print(FinalText(Documen, WordsSe))