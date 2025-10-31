import streamlit as st
import requests
import json
from openai import OpenAI
import os

DATA_GOV_API_KEY = "valid_dataset_gov_api_key_here"
OPENAI_API_KEY = "sk-proj-YourAPIKeyHere"



st.set_page_config(page_title="Agri-Climate Chatbot by Danish Adnaan", page_icon="🌾", layout="wide")

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize chat history
if 'messages' not in st.session_state:
    st.session_state.messages = []

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def search_data_gov(search_term, max_results=5):
    """Search data.gov.in for datasets"""
    url = "https://api.data.gov.in/api/3/action/package_search"
    headers = {'api-key': DATA_GOV_API_KEY}
    params = {'q': search_term, 'rows': max_results}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('success'):
            return data['result']['results']
        return []
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return []

def parse_user_question(question):
#Defining LLM for Chatbots
    prompt = f"""Analyze this question about Indian agriculture/climate and extract:
1. What data is needed (e.g., crop production, rainfall, yield)
2. Geographic entities (states, districts)
3. Crops mentioned (if any)
4. Time period (years)
5. Type of operation (compare, analyze, find max/min, trend)

Question: {question}

Return as JSON with keys: data_needed, states, crops, years, operation
"""
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Error parsing question: {e}")
        return {}

def generate_search_queries(parsed_info):
    queries = []
    
    data_needed = parsed_info.get('data_needed', '').lower()
    states = parsed_info.get('states', [])
    crops = parsed_info.get('crops', [])
    
    # Agriculture-related searches
    if any(term in data_needed for term in ['production', 'crop', 'yield', 'area']):
        if crops:
            queries.append(f"crop production {' '.join(crops)}")
        else:
            queries.append("district crop production statistics")
        
        if states:
            queries.append(f"agricultural statistics {' '.join(states)}")
    
    # Climate-related searches
    if any(term in data_needed for term in ['rainfall', 'weather', 'climate', 'temperature']):
        if states:
            queries.append(f"rainfall {' '.join(states)}")
        else:
            queries.append("rainfall statistics")
    
    # Default fallback
    if not queries:
        queries.append("agriculture statistics india")
    
    return queries

def generate_answer(question, parsed_info, datasets):
    """Use LLM to generate a comprehensive answer with citations"""
    # Format dataset information
    dataset_info = "\n\n".join([
        f"Dataset {i+1}:\n"
        f"Title: {ds.get('title', 'Unknown')}\n"
        f"Organization: {ds.get('organization', {}).get('title', 'Unknown')}\n"
        f"Description: {ds.get('notes', 'No description')[:200]}...\n"
        f"URL: https://data.gov.in/dataset/{ds.get('name', '')}"
        for i, ds in enumerate(datasets[:5])
    ])
    
    prompt = f"""You are an expert analyst of Indian agricultural and climate data.
User Question: {question}
Parsed Information: {json.dumps(parsed_info, indent=2)}
Available Datasets from data.gov.in: {dataset_info}

Based on the available datasets, provide a comprehensive answer to the user's question.

IMPORTANT INSTRUCTIONS:
1. Reference specific datasets using [Dataset N] notation
2. Explain what data is available to answer the question
3. If exact data is not available, suggest what the datasets contain
4. Provide data-backed insights where possible
5. Format your response with clear sections and bullet points
6. Add a "Sources" section at the end listing all referenced datasets

If the datasets do not contain enough information to fully answer the question, be honest about limitations.
"""
    
    try:
        response = openai_client.chat.completions.create(model="gpt-4",messages=[{"role": "user", "content": prompt}],
            temperature=0.3,max_tokens=1500)
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating answer: {e}"

# =============================================================================
# USER INTERFACE
# =============================================================================

# Header
st.title("🌾 Indian Agriculture & Climate Intelligence by Danish Adnaan")
st.caption("Chat with the Chatbot about India's agricultural data and climate patterns")

# Sidebar
with st.sidebar:
    st.header(" About")
    st.markdown("""
    This system queries live data from India's Open Government Data portal to answer your questions.
    
    All responses include citations to original datasets. using the mentioned datasets API.
    """)
    
    st.header("💡 Example Questions")
    examples = [
        "Compare rice production in Punjab and Haryana",
        "Rainfall trends in Maharashtra over last 5 years",
        "Which state produces most wheat?",
        "Cotton production statistics in Gujarat",
        "District-wise crop production in Karnataka"
    ]
    
    for example in examples:
        if st.button(example, key=f"ex_{hash(example)}", use_container_width=True):
            st.session_state.clicked_example = example
        
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle example button clicks
if 'clicked_example' in st.session_state:
    user_input = st.session_state.clicked_example
    del st.session_state.clicked_example
else:
    user_input = st.chat_input("Ask a question about Indian agriculture or climate...")

# Process user input
if user_input:
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Generate response
    with st.chat_message("assistant"):
        with st.status(" Processing your question...", expanded=True) as status:
            
            # Step 1: Parse the question
            st.write(" Understanding your question...")
            parsed_info = parse_user_question(user_input)
            
            if parsed_info:
                st.write(f"✓ Identified: {parsed_info.get('operation', 'analysis')} on {parsed_info.get('data_needed', 'agricultural data')}")
            
            # Step 2: Generate search queries
            st.write(" Searching data.gov.in...")
            search_queries = generate_search_queries(parsed_info)
            
            # Step 3: Fetch datasets
            all_datasets = []
            for query in search_queries[:2]:  # Limit to 2 searches
                st.write(f"   Searching: '{query}'")
                datasets = search_data_gov(query, max_results=3)
                all_datasets.extend(datasets)
            
            st.write(f"✓ Found {len(all_datasets)} relevant datasets")
            
            # Step 4: Generate answer
            st.write(" Generating comprehensive answer...")
            answer = generate_answer(user_input, parsed_info, all_datasets)
            
            status.update(label="✅ Complete!", state="complete", expanded=False)
        
        # Display the answer
        st.markdown(answer)
        
        # Save to chat history
        st.session_state.messages.append({"role": "assistant", "content": answer})

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.85rem;'>
    Powered by data.gov.in | Ministry of Agriculture & IMD | OpenAI GPT-4
</div>
""", unsafe_allow_html=True)

#########################################################################################################