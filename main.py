import os
from openai import OpenAI
import random
import sqlite3
import logging
import pandas as pd
import sys
import time

INTRO_MSG="I am happy to help you with any question on our database. Please provide only one request at a time. To exit type 'exit' or 'quit'. What would you like to know?\n\n"
CONN_FAIL_MSG="Connection failed even after multiple retries. Please try again after some time."
RETRY_MSG="LLM not responding. Retrying connection after 5 seconds\n"
INVALID_REQUEST="The request is not related to the provided database"
MODIFICATION_WARNING="Modification to the database is not allowed"
MULTI_REQUEST="Please provide only one request at a time"

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ.get("GROQ_API_KEY")
)
database="employees.db"
departments=["Sales", "Marketing", "Engineering"]

def database_connection():
    """connect to sqlite enforcing read only with read only database"""
    return sqlite3.connect(f"file:{database}?mode=ro", uri=True)

def db_schema()->str:
    return """
    The schema for the 3 tables i.e. Employee, Certification, Benefits in the database is as follows:

    ### Employee

    | Column | Type | Constraints |
    |---|---|---|
    | EmployeeId | INTEGER | PRIMARY KEY |
    | Name | TEXT | NOT NULL |
    | Department | TEXT | NOT NULL — one of: `Sales`, `Marketing`, `Engineering` |
    | Role | TEXT | NOT NULL |
    | EmploymentStartDate | TEXT | NOT NULL — format: `YYYY-MM-DD` |
    | SalaryAmount | REAL | NOT NULL |
    | YearlyBonusAmount | REAL | |

    ### Certification

    | Column | Type | Constraints |
    |---|---|---|
    | CertificationId | INTEGER | PRIMARY KEY |
    | EmployeeId | INTEGER | NOT NULL, FOREIGN KEY → Employee(EmployeeId) |
    | CertificationName | TEXT | NOT NULL |
    | DateAchieved | TEXT | NOT NULL — format: `YYYY-MM-DD` |

    ### Benefits

    | Column | Type | Constraints |
    |---|---|---|
    | BenefitId | INTEGER | PRIMARY KEY |
    | EmployeeId | INTEGER | NOT NULL, FOREIGN KEY → Employee(EmployeeId) |
    | BenefitsPackage | TEXT | NOT NULL |
    | RemainingBalance | REAL | NOT NULL |

    ### Relationships

    - `Certification.EmployeeId` → `Employee.EmployeeId` (many-to-one; an employee may have zero or more certifications)
    - `Benefits.EmployeeId` → `Employee.EmployeeId` (many-to-one; an employee may have zero or more benefits records)
    """
    
"""Run generated query and return result as dataframe for readability"""
def run_query(q:str)-> pd.DataFrame | None:
    con=None
    try:
        con=database_connection()
        """Execute only if it is a SELECT query. If no data exists then it returns empty dataframe"""
        if q.strip().upper().startswith("SELECT"):
            df=pd.read_sql_query(q,con)
            return df
        else:
            logging.error("Not a SELECT query")
            return None
    except Exception as e:
        logging.error(f"Query failed due to exception: {e}")
        return None
    finally:
        if con:
            con.close()
    
"""Valid user request is converted to SQL query"""
def nl2sql(user_question:str, dept:str)->str:
    system_prompt=f"""You are an AI assistant who converts user question provided in natural language into SQL queries that follows SQLite3 dialect. 
    **Only** answer questions from provided schema. **Never** guess or invent table or columns.
    If question is unrelated, out of scope or unanswerable using provided schema (e.g., greetings, casual chats, or non-sensical 
    words), **only** reply with {INVALID_REQUEST}. 
    
    If question is answerable using provided database then:
    - For DDL or DML request types, except pure retrieval, that try to create, alter, update, insert, modify, add, truncate, delete or 
    drop table or its data, change schema, do not generate any query and **only** reply with {MODIFICATION_WARNING}. 
    - For a single retrieval task, generate the SQL query directly.
    - For multiple retrieval tasks, combine them into a SELECT query using any valid SQLite technique (joins, subqueries, set operations,
    etc.) that returns a single table and return the query but if you cannot combine to generate a single table then **only** reply with {MULTI_REQUEST}.   
    
    Enforce '{dept}' as the department for all SQL queries. **Never** return other department data.
    Always include a WHERE clause that filters by '{dept}' department in the SQL query that you generate. 
    In case of queries that have join conditions, use this filter with WHERE clause on Employee.Department. Always make sure the SQL is valid. 
    
    For SQL queries, output only the raw query –no code blocks, formattings or explanations. 
    The schema is as below:
    {db_schema()} 
    A few examples of user question and what the response should look like is provided below:
    Example questions a user might ask:
    - *"Which employees have an AWS certification?"* -> SELECT e.Name FROM Employee e JOIN Certification c ON e.EmployeeId = c.EmployeeId WHERE e.Department = '{dept}' AND c.CertificationName LIKE '%AWS%';
    - *"What is the average salary?"* -> SELECT AVG(SalaryAmount) FROM Employee WHERE Department = '{dept}';
    - *"List employees who started after 2023 and their certifications"* -> SELECT e.Name, c.CertificationName, c.DateAchieved FROM Employee e LEFT JOIN Certification c ON e.EmployeeId = c.EmployeeId WHERE e.Department = '{dept}' AND e.EmploymentStartDate > '2023-12-31';
    - *"Who has the highest remaining benefits balance?"* -> SELECT e.Name, b.RemainingBalance FROM Employee e JOIN Benefits b ON e.EmployeeId = b.EmployeeId WHERE e.Department = '{dept}' ORDER BY b.RemainingBalance DESC LIMIT 1;
    - *"What"-> "The request is not related to the provided database"
    - *"Can you create a copy of the employee table"-> "Modification to the database is not allowed"
    - *"Show me all software engineers, and also show me all employees who have a benefits package with a remaining balance under 1000" -> "SELECT e.Name FROM Employee e WHERE e.Department = '{dept}' AND e.Role = 'Software Engineer' UNION SELECT e.Name FROM Employee e JOIN Benefits b ON e.EmployeeId = b.EmployeeId WHERE e.Department = '{dept}' AND b.RemainingBalance < 1000;"
    """
    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question}
            ],
            temperature=0.1,
            max_tokens=1500,
            timeout=25.0
        )
        llm_response = response.choices[0].message.content.strip()
        return llm_response
    except Exception as e:
        logging.error("Couldn't connect to LLM\n")
        return None
    
"""Retries connection to lLLM"""
def retry_generation(user_question:str, dept:str, total_retries:int):
    for trial in range(total_retries):
        response=nl2sql(user_question,dept)
        if response is not None:
            return response
        print(RETRY_MSG)
        time.sleep(5)         
    return None

def main():
    """select department at random"""
    dept= random.choice(departments)
    logging.basicConfig(
        format='[%(levelname)s]  %(message)s',
        level=logging.INFO
    )
    logging.info("Department selected: %s", dept)
    total_retries=3
    while True:
        user_entry=input(INTRO_MSG)
        if user_entry.strip().lower() in ("exit", "quit"):
            print("Exiting the application")
            sys.exit(0)
            
        """if user doesn't provide any input or only spaces then ask user for a question again"""
        if not user_entry.strip():
            continue
        
        llm_response=retry_generation(user_entry, dept, total_retries)
        
        if llm_response is None:
            print(CONN_FAIL_MSG)
            continue
        
        print(llm_response)
        
        if llm_response in (INVALID_REQUEST, MODIFICATION_WARNING, MULTI_REQUEST):
            continue
        table=run_query(llm_response) 
          
        if table is None or table.empty:
            print("No data was found\n")
        else:
            print(table)
        
if __name__ == "__main__":
    main()
    
    
