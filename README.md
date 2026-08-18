# SETUP AND INSTALLATION INSTRUCTIONS:

Clone the repository

Install dependencies like openai and pandas using pip install

Create a .env file and mention API key as follows:

GROQ_API_KEY= enter API key here

Mention the model in main.py (This project uses GROQ API and openai/gpt-oss-120b model).

# HOW TO RUN THE APPLICATION

Run python main.py in terminal

To exit type 'exit' or 'quit'

# ARCHITECTURE

I have assumed that only SELECT queries should be made to run on the data. My reasoning is as follows: 
- The questionnaire examples focus on retrieval rather than making changes to the data. 
- The question asks to “return results” and not to update/insert/delete. 
- Also, it will be dangerous to ask an LLM to create queries that can change data as it may hallucinate and insert incorrect data (If we are to consider INSERT, UPDATE or DELETE queries then that would require close attention to foreign and primary keys as the deletion of one row in a table might only be possible if the reference is deleted first. Also, it would be necessary to have important checks like ensuring UPDATE queries have WHERE condition stated).


## System prompt

System prompt addresses nuances like considering only SELECT queries and rejecting queries that modify the structure or data.

It also ensures unrelated and vague questions/words are rejected with a message. 

Few shot prompting was implemented by providing variety of examples for context.

## DESIGN
run_query() checks that only queries starting with SELECT are executed so that queries that seeped through LLM response are filtered.

Connection failures and empty tables are handled

Appropriate messages are displayed for user information and logging purposes

Retry logic and timeout are implemented in case of LLM connection failure or unresponsive API

Pandas is being used to display results in readable format

db_schema() function is used to store schema instead of a variable to future proof it in case we directly need to extract the schema from db later

It allows multiple SELECT queries if it returns a single table example "UNION" statements

If the query returns multiple tables then it replies with "Please provide only one request at a time".

## FRAMEWORK CHOSEN

I didn’t choose semantic kernel framework or langchain as we have a simple and straight forward workflow use case which doesn’t require working with multiple tools or multiple agents. I have selected lightweight script over custom agent loop as this is a simple workflow involving only 3 tables(queries rarely become complex) and it gives me more control to add guardrails as agentic loop might hallucinate during the loops and remove the mandatory guardrail for department. If generated query already has a WHERE clause then LLM would append the guardrail condition and if query doesn’t have any WHERE clause then it will add the WHERE clause with the guardrail.


# AI TOOLS USED

Chatgpt was used to search for free LLMs and available models in Groq

Genrated queries were doubly validated using AI

