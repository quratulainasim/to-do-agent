import streamlit as st
import asyncio
import os
from supabase import create_client, Client
from openai import AsyncOpenAI
from agents import Agent, Runner, function_tool, OpenAIChatCompletionsModel, ModelSettings
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]

if not all([SUPABASE_URL, SUPABASE_KEY, GOOGLE_API_KEY]):
    st.error("Missing environment variables. Please set SUPABASE_URL, SUPABASE_KEY, and GOOGLE_API_KEY.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

client = AsyncOpenAI(
    api_key=GOOGLE_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/"
)

model = OpenAIChatCompletionsModel(
    model="gemini-1.5-flash",
    openai_client=client
)

st.set_page_config(page_title="To-Do Manager", layout="centered")
page = st.sidebar.selectbox("Choose a page", ["📋 Manage To-Dos", "📜 Task History"])

@function_tool
async def add_task(user_id: str, task: str) -> str:
    """Add a task for the given user."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: supabase.table("todos").insert({
        "user_id": user_id,
        "task": task
    }).execute())
    return f"Task '{task}' added for user {user_id}."

@function_tool
async def remove_all_tasks(user_id: str) -> str:
    """Remove all tasks for the given user."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: supabase.table("todos").delete().eq("user_id", user_id).execute())
    return f"All tasks removed for user {user_id}."

@function_tool
async def list_tasks(user_id: str) -> str:
    """List all tasks for the given user."""
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, lambda: supabase.table("todos").select("task").eq("user_id", user_id).execute())
    tasks = [item["task"] for item in res.data]
    if not tasks:
        return f"No tasks found for user {user_id}."
    return "\n".join(f"{idx+1}. {task}" for idx, task in enumerate(tasks))

# Initialize agent
agent = Agent(
    name="TO-DO MANAGER",
    instructions="You are a to-do manager to manage the user's tasks. You handle commands to add, remove, or list tasks. The user must provide a user_id and task details when required. If the user_id or task is missing, prompt them to provide the necessary details. Only process to-do-related commands.",
    tools=[add_task, remove_all_tasks, list_tasks],
    model=model,
    model_settings=ModelSettings(tool_choice="required")
)

async def get_all_tasks():
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, lambda: supabase.table("todos").select("*").execute())
    return res.data if res.data else []

async def run_agent_async(prompt):
    return await Runner.run(agent, prompt)

if page == "📋 Manage To-Dos":
    st.title("📋 Manage To-Dos")


    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        role = msg["role"].capitalize()
        content = msg["content"]
        with st.chat_message(role.lower()):
            st.markdown(content)

    prompt = st.chat_input("Enter your to-do command (e.g., 'my user_id is sara add task Buy groceries')")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            result = asyncio.run(run_agent_async(prompt))
            reply = result.final_output
            st.session_state.messages.append({"role": "assistant", "content": reply})
            with st.chat_message("assistant"):
                st.markdown(reply)
        except Exception as e:
            st.error(f"An error occurred: {e}")

elif page == "📜 Task History":
    st.title("📜 Task History")


    try:
        tasks = asyncio.run(get_all_tasks())
    except Exception as e:
        st.error(f"Failed to retrieve tasks: {e}")
        tasks = []

    if not tasks:
        st.warning("No tasks found.")
    else:
        st.subheader("All Tasks")
        for task in tasks:
            user_id = task.get("user_id", "Unknown")
            content = task.get("task", "Unknown")
            label = f"**Task for {user_id}**"
            st.warning(f"{label}\n\n{content}")


# if "auto_processed" not in st.session_state:
#     st.session_state.auto_processed = True
#     try:
#         result = asyncio.run(run_agent_async("my user_id is ani and my task is i love you add this"))
#         st.session_state.messages.append({"role": "user", "content": "my user_id is ani and my task is i love you add this"})
#         st.session_state.messages.append({"role": "assistant", "content": result.final_output})
#     except Exception as e:
#         st.error(f"Failed to auto-process task: {e}")
