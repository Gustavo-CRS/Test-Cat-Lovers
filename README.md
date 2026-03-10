# 🐾 UOLCatLovers - Desafio Técnico: Engenharia de Dados

Este projeto resolve o problema de extração, armazenamento e disponibilização de dados sobre gatos (Cat Facts) para o time de Analytics, evoluindo de uma solução local simples para uma arquitetura escalável e resiliente na nuvem (Google Cloud Platform).

O projeto foi dividido em três etapas principais, detalhadas abaixo.

---

## 🛠️ Etapa 1: Ingestão Local (Script Python)

Como solução inicial para a validação da ideia, foi desenvolvido um script em Python que consome a API [Cat Facts](https://alexwohlbruck.github.io/cat-facts/docs/) e salva os dados em um arquivo CSV local.

> ⚠️ **Aviso Importante: Indisponibilidade da API de Origem (HTTP 503)**
> 
> Durante o desenvolvimento e execução deste teste, a API fornecida (`https://cat-fact.herokuapp.com`) encontrava-se indisponível, retornando o erro **HTTP 503 (Service Unavailable)**. 
> 
> Como fontes de dados instáveis são comuns em cenários reais, o script foi construído com foco em **resiliência**. Foram implementados blocos de `try/except` e `raise_for_status()` para capturar a falha de forma graciosa. Em vez de causar um *crash* no pipeline, o código registra o erro estruturado no sistema de *logging* e encerra a execução de forma controlada. A lógica de extração e conversão tabular (parsing) está totalmente implementada e pronta para processar o *payload* assim que o serviço for restabelecido.

### Como executar
1. Certifique-se de ter o Python 3 instalado.
2. Instale as dependências do projeto:
   ```bash
   pip install -r requirements.txt
   ```
3. Execute o script principal:
   ```bash
   python extract_cat_facts.py
   ```
4. Em condições normais da API, o arquivo `cat_facts.csv` será gerado no diretório raiz contendo os dados extraídos.

**Destaques do código:**
* Tratamento de paginação/limites (uso combinado dos endpoints `/facts` e `/facts/random`).
* Prevenção de duplicatas utilizando o `_id` da origem.
* Logging estruturado para facilitar o *troubleshooting* e monitoramento.

---

## ☁️ Etapa 2: Arquitetura em Nuvem (Google Cloud Platform)

Com o crescimento do aplicativo, a solução local não seria mais viável. A arquitetura foi então redesenhada para a nuvem do GCP, adotando os princípios de *Modern Data Stack* (MDS) e a **Arquitetura Medalhão** (Bronze, Silver, Gold).

![Arquitetura GCP](https://github.com/Gustavo-CRS/Test-Cat-Lovers/blob/main/desenho_arquitetura.png)

### Decisões de Arquitetura e Fluxo de Dados:

* **Ingestão Serverless (Cloud Function):** Uma Cloud Function é acionada periodicamente pelo **Cloud Scheduler** para realizar as requisições à API. Essa abordagem não exige gerenciamento de servidores e o custo é baseado apenas no tempo de execução.
* **Landing Zone / Raw (Cloud Storage):** Antes de chegar ao Data Warehouse, o payload JSON bruto da API é salvo em um bucket do GCS. Isso garante um *Data Lake* puro, servindo como backup imutável. Se o contrato da API mudar e quebrar o fluxo downstream, os dados históricos estão protegidos e prontos para reprocessamento.
* **Camada Bronze (BigQuery via BQ Data Transfer):** A ingestão do GCS para a camada Bronze do BQ é feita via *BigQuery Data Transfer Service*, eliminando a necessidade de escrever e manter código extra para o processo de *Load*. O dado entra no formato tabular com a mesma granularidade da origem tendo apenas o acréscimo do campo `loaded_at` como metadado.
* **Transformação (dbt):** A passagem da camada Bronze para a Silver (dados limpos e padronizados) e Gold (regras de negócio e agregações) é gerenciada pelo **dbt**. Isso garante controle de versão das transformações, testes de qualidade de dados (*Data Contracts*) e documentação de linhagem nativa.
* **Observabilidade e Alertas:** A saúde do pipeline é garantida pelo **Cloud Logging** (recebendo logs da Cloud Function para monitorar falhas como timeouts 503) e integrações do dbt com o **Slack**, alertando o time de engenharia imediatamente caso testes de qualidade de dados falhem na transformação.
* **Consumo (IAM):** O time de Analytics consome os dados diretamente da camada Gold. O acesso é governado via IAM (Identity and Access Management) do GCP, garantindo o princípio do menor privilégio.

---

## 📊 Etapa 3: Modelagem de Dados no BigQuery

Para atender às necessidades do time de Analytics em realizar suas próprias consultas, foi especificado o esquema da tabela principal de fatos na camada Silver/Gold. 

Abaixo está o **DDL** de criação da tabela, desenhado no BigQuery:

```sql
CREATE OR REPLACE TABLE `uolcatlovers.analytics_cat_facts.cat_facts_silver`
(
    id STRING NOT NULL OPTIONS(description="Identificador único do fato gerado pela API (MongoDB ObjectId)"),
    text STRING NOT NULL OPTIONS(description="O texto contendo o fato sobre o gato"),
    type STRING OPTIONS(description="Tipo de animal, padrão 'cat'"),
    deleted BOOLEAN OPTIONS(description="Flag indicando se o fato foi deletado na origem"),
    source STRING OPTIONS(description="Origem do fato (ex: 'user', 'api')"),
    sent_count INT64 OPTIONS(description="Número de vezes que este fato foi enviado/compartilhado"),
    created_at TIMESTAMP OPTIONS(description="Data e hora de criação do fato na origem"),
    updated_at TIMESTAMP OPTIONS(description="Data e hora da última atualização do fato na origem"),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP() OPTIONS(description="Metadado: Data e hora em que o registro foi ingerido no BigQuery")
)
PARTITION BY DATE(loaded_at)
CLUSTER BY source, type;
```

### Considerações Técnicas da Modelagem:
* **Tipagem Estrita:** Campos de data (`created_at`, `updated_at`) foram tipados como `TIMESTAMP`, permitindo que o time de Analytics utilize funções de tempo nativas do BigQuery sem necessidade de *casting*.
* **Metadados de Ingestão:** A inclusão da coluna `loaded_at` com o `CURRENT_TIMESTAMP()` permite a auditoria dos dados, separando o momento em que o evento ocorreu do momento em que foi processado no Data Warehouse.
* **Particionamento:** A tabela é particionada por dia com base na coluna `loaded_at`. Como o volume de dados deve crescer exponencialmente, isso reduzirá drasticamente os custos e o tempo de processamento (*scan*) em consultas com filtros temporais.
* **Clusterização:** A clusterização pelas colunas `source` e `type` organiza fisicamente os dados, acelerando agregações e filtros comuns em relatórios analíticos.
* **Data Catalog (Governança):** O uso do parâmetro `OPTIONS(description=...)` garante que o esquema já nasça documentado, integrando-se automaticamente ao GCP Data Catalog e dando autonomia aos analistas de dados.

## 🔍 Etapas 4 e 5: Consultas SQL (Analytics e QA)

### 4. Consulta para o time de Analytics (Estudo de Caso - Agosto/2020)

Query para extrair os fatos atualizados em agosto de 2020 de forma performática:

```sql
SELECT 
    *
FROM 
    `uolcatlovers.analytics_cat_facts.cat_facts_silver`
WHERE 
    updated_at >= TIMESTAMP('2020-08-01 00:00:00')
    AND updated_at < TIMESTAMP('2020-09-01 00:00:00');
```

---

### 5. Amostra de 10% para o ambiente de QA (Exportação para CSV)

Query para extrair aleatoriamente 10% da base contendo apenas as colunas solicitadas.

```sql
EXPORT DATA OPTIONS(
  uri='gs://[NOME_DO_SEU_BUCKET]/amostras_qa/cat_facts_sample_*.csv',
  format='CSV',
  overwrite=true,
  header=true,
  field_delimiter=','
) AS
SELECT 
    text, 
    created_at, 
    updated_at
FROM 
    `uolcatlovers.analytics_cat_facts.cat_facts_silver` 
WHERE 
    RAND() < 0.1;
```