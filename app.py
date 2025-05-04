# JIRA Resource Management App with AI PM Buddy
# Integrated application that combines visualization dashboards with AI-powered project management assistant

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import xlsxwriter
from openai import OpenAI
from datetime import datetime
import os
from utils import load_data

# Page configuration and title
st.set_page_config(
    page_title="JIRA Resource Management App",
    page_icon="📊",
    layout="wide"
)

# Sidebar navigation
st.sidebar.title("📊 JIRA Resource Management")

# ---------- File Upload ----------
fallback_file = "enriched_jira_project_data.xlsx"
uploaded_file = st.sidebar.file_uploader("Upload your JIRA Excel file", type="xlsx")

if st.sidebar.button("📂 Load Sample Project Data"):
    if os.path.exists(fallback_file):
        uploaded_file = open(fallback_file, "rb")
        st.sidebar.success("Loaded default file: enriched_jira_project_data.xlsx")

# ---------- Load Data ----------
# Initialize global variables
issues_df, skills_df, worklogs_df, leaves_df = None, None, None, None

# Load data from file
if uploaded_file is not None:
    issues_df, skills_df, worklogs_df, leaves_df = load_data(uploaded_file)

# ---------- Navigation Tabs ----------
nav_options = [
    "📊 Dashboard",
    "📅 Gantt Chart",
    "🚦 Traffic Light Matrix",
    "📈 Sprint Burnup",
    "📋 PM Daily Brief",
    "📡 Radar Chart",
    "🫧 Bubble Chart",
    "🌡 Calendar Heatmap",
    "🌳 Treemap",
    "🤖 AI PM Buddy"
]

nav_selection = st.sidebar.radio("Navigation", nav_options)

# ---------- Gantt Chart ----------
def gantt_chart():
    st.title("📅 Gantt Chart - Timeline by Assignee")
    if issues_df is None:
        st.warning("Please upload a valid JIRA Excel file.")
        return
    issues_df['Start Date'] = pd.to_datetime(issues_df['Start Date'], errors='coerce')
    issues_df['Due Date'] = pd.to_datetime(issues_df['Due Date'], errors='coerce')
    gantt_data = issues_df.dropna(subset=['Start Date', 'Due Date'])
    if gantt_data.empty:
        st.warning("No valid start and due dates available for Gantt chart visualization.")
        return
    fig = px.timeline(
        gantt_data,
        x_start="Start Date",
        x_end="Due Date",
        y="Assignee",
        color="Project",
        hover_name="Summary",
        title="Gantt Chart by Assignee"
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)

# ---------- Traffic Light Matrix ----------
def traffic_light_matrix():
    st.title("🚦 Traffic Light Matrix - Task Monitoring")
    if issues_df is None:
        st.warning("Please upload a valid JIRA Excel file.")
        return
    today = pd.to_datetime("today").normalize()
    issues_df['Due Date'] = pd.to_datetime(issues_df['Due Date'], errors='coerce')
    summary = issues_df.groupby('Assignee').agg(
        total_tasks=('Issue Key', 'count'),
        overdue_tasks=('Due Date', lambda d: (d < today).sum())
    ).reset_index()
    summary['Status'] = summary.apply(
        lambda row: '🟢' if row['overdue_tasks'] == 0 else (
            '🟠' if row['overdue_tasks'] < row['total_tasks'] * 0.5 else '🔴'
        ), axis=1
    )
    st.dataframe(summary)

# ---------- Sprint Burnup ----------
def sprint_burnup():
    st.title("📈 Sprint Burnup Chart")
    if issues_df is None:
        st.warning("Please upload a valid JIRA Excel file.")
        return
    issues_df['Start Date'] = pd.to_datetime(issues_df['Start Date'], errors='coerce')
    issues_df['Due Date'] = pd.to_datetime(issues_df['Due Date'], errors='coerce')
    if issues_df['Start Date'].isna().all() or issues_df['Due Date'].isna().all():
        st.warning("Start Date or Due Date missing in all records. Cannot build burnup chart.")
        return
    date_range = pd.date_range(start=issues_df['Start Date'].min(), end=issues_df['Due Date'].max())
    burnup_data = pd.DataFrame({'Date': date_range})
    burnup_data['Completed'] = burnup_data['Date'].apply(
        lambda d: issues_df[(issues_df['Status'] == 'Done') & (issues_df['Due Date'] <= d)]['Story Points'].sum()
    )
    burnup_data['Total Scope'] = issues_df['Story Points'].sum()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=burnup_data['Date'], y=burnup_data['Completed'], mode='lines+markers', name='Completed'
    ))
    fig.add_trace(go.Scatter(
        x=burnup_data['Date'], y=[burnup_data['Total Scope'].iloc[0]]*len(burnup_data),
        mode='lines', name='Total Scope', line=dict(dash='dash')
    ))
    fig.update_layout(title='Sprint Burnup Chart', xaxis_title='Date', yaxis_title='Story Points')
    st.plotly_chart(fig, use_container_width=True)

# ---------- Radar Chart ----------
def radar_chart():
    st.title("📡 Radar Chart - Resource Load by Skill")
    if issues_df is None or skills_df is None or worklogs_df is None:
        st.warning("Please upload a valid JIRA Excel file.")
        return
    if 'Resource' not in worklogs_df.columns or 'Resource' not in skills_df.columns:
        st.error("Missing 'Resource' column in worklogs or skills data.")
        return
    combined = pd.merge(worklogs_df, skills_df, on='Resource', how='inner')
    if 'Time Spent (hrs)' not in combined.columns or 'Skillset' not in combined.columns:
        st.error("Missing required columns in merged dataset.")
        return
    radar_data = combined.groupby(['Skillset', 'Resource'])['Time Spent (hrs)'].sum().reset_index()
    if radar_data.empty:
        st.warning("No merged worklog and skill data available.")
        return
    for skill in radar_data['Skillset'].unique():
        df = radar_data[radar_data['Skillset'] == skill]
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=df['Time Spent (hrs)'],
            theta=df['Resource'],
            fill='toself',
            name=skill
        ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True)),
            showlegend=True,
            title=f"Load Balance for Skill: {skill}"
        )
        st.plotly_chart(fig, use_container_width=True)

# ---------- PM Daily Brief ----------
def pm_daily_brief():
    st.title("📝 Project Manager Daily Brief")
    if issues_df is None:
        st.warning("Please upload a valid JIRA Excel file.")
        return

    today = pd.to_datetime("today").normalize()
    issues_df['Start Date'] = pd.to_datetime(issues_df['Start Date'], errors='coerce')
    issues_df['Due Date'] = pd.to_datetime(issues_df['Due Date'], errors='coerce')

    unassigned = issues_df[issues_df['Assignee'].isna()]
    due_soon = issues_df[issues_df['Due Date'].between(today, today + pd.Timedelta(days=7), inclusive='both')]
    stuck = issues_df[(issues_df['Status'] == 'In Progress') & ((today - issues_df['Start Date']).dt.days > 7)]
    missing_est = issues_df[issues_df['Original Estimate (days)'].isna() | issues_df['Story Points'].isna()]
    overdue = issues_df[issues_df['Due Date'] < today]

    st.subheader("🔧 Action Required")
    if not unassigned.empty: st.markdown("**🔲 Unassigned Tasks**"); st.dataframe(unassigned)
    if not due_soon.empty: st.markdown("**🗓 Tasks Due This Week**"); st.dataframe(due_soon)
    if not stuck.empty: st.markdown("**🔄 Stuck Tasks (In Progress > 7 days)**"); st.dataframe(stuck)

    st.subheader("🚨 Alerts & Notifications")
    if not missing_est.empty: st.markdown("**⚠️ Missing Estimates**"); st.dataframe(missing_est)
    if not overdue.empty: st.markdown("**⏰ Overdue Tasks**"); st.dataframe(overdue)

    st.subheader("🤖 Recommendations")
    st.markdown("- Reassign unassigned or stuck tasks.")
    st.markdown("- Alert assignees with overdue items.")
    st.markdown("- Review items due this week.")

    brief = f"""
    === PROJECT MANAGER DAILY BRIEF ===
    - {len(unassigned)} unassigned tasks
    - {len(due_soon)} tasks due this week
    - {len(stuck)} tasks in progress > 7 days
    - {len(missing_est)} tasks missing estimates
    - {len(overdue)} overdue tasks
    """
    st.download_button("📄 Download Brief as TXT", brief, file_name="PM_Daily_Brief.txt")

# ---------- Stacked Bar Chart ----------
def stacked_bar_resource_utilization():
    st.title("📊 Stacked Bar Chart - Resource Utilization by Week")
    if worklogs_df is None:
        st.warning("Please upload a valid JIRA Excel file.")
        return

    if 'Date' not in worklogs_df.columns or 'Resource' not in worklogs_df.columns:
        st.error("Worklogs must include 'Date' and 'Resource' columns.")
        return

    worklogs_df['Date'] = pd.to_datetime(worklogs_df['Date'], errors='coerce')
    worklogs_df = worklogs_df.dropna(subset=['Date'])
    worklogs_df['Week'] = worklogs_df['Date'].dt.strftime('%Y-%U')
    grouped = worklogs_df.groupby(['Week', 'Resource'])['Time Spent (hrs)'].sum().reset_index()

    if grouped.empty:
        st.warning("No worklog data to display.")
        return

    fig = px.bar(
        grouped,
        x='Week',
        y='Time Spent (hrs)',
        color='Resource',
        title='Resource Utilization by Week',
        text_auto=True
    )
    fig.update_layout(barmode='stack', xaxis_title='Week', yaxis_title='Hours Worked')
    st.plotly_chart(fig, use_container_width=True)

# ---------- Bubble Chart: Overload vs. Velocity ----------
def bubble_chart_overload_velocity():
    st.title("🫧 Bubble Chart - Overload vs. Velocity")
    if worklogs_df is None or issues_df is None:
        st.warning("Please upload a valid JIRA Excel file.")
        return

    worklogs_df['Date'] = pd.to_datetime(worklogs_df['Date'], errors='coerce')
    worklogs_df['Week'] = worklogs_df['Date'].dt.strftime('%Y-%U')
    actuals = worklogs_df.groupby(['Week', 'Resource'])['Time Spent (hrs)'].sum().reset_index()

    if 'Story Points' not in issues_df.columns or 'Assignee' not in issues_df.columns:
        st.error("Issues sheet must contain 'Assignee' and 'Story Points'.")
        return

    velocity = issues_df.groupby('Assignee')['Story Points'].sum().reset_index()
    velocity.columns = ['Resource', 'Story Points']
    merged = pd.merge(actuals, velocity, on='Resource', how='left')
    merged = merged.dropna()

    if merged.empty:
        st.warning("Insufficient data for bubble chart.")
        return

    fig = px.scatter(
        merged,
        x='Story Points',
        y='Time Spent (hrs)',
        size='Time Spent (hrs)',
        color='Resource',
        hover_name='Resource',
        title='Overload vs. Velocity Bubble Chart',
        labels={'Story Points': 'Velocity', 'Time Spent (hrs)': 'Actual Load'}
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------- Calendar Heatmap ----------
def calendar_heatmap():
    st.title("🌡 Calendar Heatmap - Resource-wise Utilization")
    if worklogs_df is None:
        st.warning("Please upload a valid JIRA Excel file.")
        return

    if 'Date' not in worklogs_df.columns or 'Resource' not in worklogs_df.columns:
        st.error("Missing 'Date' or 'Resource' in Worklogs data.")
        return

    worklogs_df['Date'] = pd.to_datetime(worklogs_df['Date'], errors='coerce')
    df = worklogs_df.dropna(subset=['Date'])
    df['Day'] = df['Date'].dt.date

    pivot = df.groupby(['Resource', 'Day'])['Time Spent (hrs)'].sum().reset_index()
    pivot.columns = ['Resource', 'Day', 'Hours']
    heatmap = pivot.pivot(index='Resource', columns='Day', values='Hours').fillna(0)
    heatmap = heatmap[sorted(heatmap.columns)]

    st.subheader("📆 Utilization Heatmap by Resource")
    styled_heatmap = heatmap.style.format('{:.1f}').background_gradient(cmap='viridis', axis=None, gmap=heatmap, vmin=0, vmax=heatmap.values.max())
    st.dataframe(styled_heatmap)

# ---------- Treemap: Team Resource Distribution ----------
def treemap_resource_distribution():
    st.title("🌳 Treemap - Team Resource Distribution")
    if skills_df is None:
        st.warning("Please upload a valid JIRA Excel file.")
        return

    if 'Resource' not in skills_df.columns or 'Skillset' not in skills_df.columns:
        st.error("Skills data must include 'Resource' and 'Skillset' columns.")
        return

    skills_df['Count'] = 1
    fig = px.treemap(
        skills_df,
        path=['Skillset', 'Resource'],
        values='Count',
        title="Distribution of Resources by Skillset"
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------- Dashboard ----------
def dashboard():
    st.title("📊 JIRA Resource Management Dashboard")
    if issues_df is None or skills_df is None or worklogs_df is None:
        st.warning("Please upload a valid JIRA Excel file using the sidebar.")
        st.info("Use the '📂 Load Sample Project Data' button to load sample data if available.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📅 Sprint Timeline")
        gantt_data = issues_df.dropna(subset=['Start Date', 'Due Date'])
        if not gantt_data.empty:
            mini_gantt = px.timeline(
                gantt_data.head(10),
                x_start="Start Date",
                x_end="Due Date",
                y="Assignee",
                color="Status",
                hover_name="Summary",
            )
            mini_gantt.update_yaxes(autorange="reversed")
            st.plotly_chart(mini_gantt, use_container_width=True)
    
    with col2:
        st.subheader("🚦 Task Status")
        status_counts = issues_df['Status'].value_counts()
        fig = px.pie(names=status_counts.index, values=status_counts.values)
        st.plotly_chart(fig, use_container_width=True)
    
    col3, col4 = st.columns(2)
    
    with col3:
        st.subheader("👥 Team Workload")
        if 'Resource' in worklogs_df.columns and 'Time Spent (hrs)' in worklogs_df.columns:
            workload = worklogs_df.groupby('Resource')['Time Spent (hrs)'].sum().sort_values(ascending=False)
            fig = px.bar(x=workload.index, y=workload.values)
            fig.update_layout(xaxis_title="Resource", yaxis_title="Hours")
            st.plotly_chart(fig, use_container_width=True)
    
    with col4:
        st.subheader("📈 Sprint Progress")
        total = len(issues_df)
        completed = len(issues_df[issues_df['Status'] == 'Done'])
        in_progress = len(issues_df[issues_df['Status'] == 'In Progress'])
        todo = total - completed - in_progress
        
        data = pd.DataFrame({
            'Status': ['Completed', 'In Progress', 'To Do'],
            'Count': [completed, in_progress, todo],
            'Percentage': [completed/total*100, in_progress/total*100, todo/total*100]
        })
        
        fig = px.bar(data, x='Status', y='Count', text='Percentage', 
                   color='Status', color_discrete_map={'Completed': 'green', 'In Progress': 'orange', 'To Do': 'red'})
        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

# ---------- AI PM Buddy Assistant ----------
def ai_pm_buddy_assistant():
    st.title("🤖 AI PM Buddy")
    
    # Reference global variables
    global issues_df, skills_df, worklogs_df, leaves_df
    
    # Set up tabs for different PM Buddy features
    ai_tabs = st.tabs(["Ask PM Buddy", "Smart PM Brief", "What-if Simulation", "Load Planning", "Conversation History"])
    
    # ---------- Summarize Data ----------
    try:
        issues_summary = issues_df.describe(include='all').to_string() if issues_df is not None else ""
        worklog_summary = worklogs_df.groupby('Resource')['Time Spent (hrs)'].sum().to_string() if worklogs_df is not None else ""
        skill_distribution = skills_df['Skillset'].value_counts().to_string() if skills_df is not None else ""
        leave_summary = leaves_df['Resource'].value_counts().to_string() if leaves_df is not None else ""
    
        # ---------- Analytics Summary ----------
        analytics_text = ""
        if worklogs_df is not None and not worklogs_df.empty:
            worklogs_df['Date'] = pd.to_datetime(worklogs_df['Date'], errors='coerce')
            daily_work = worklogs_df.groupby(['Resource', 'Date'])['Time Spent (hrs)'].sum().reset_index()
            overload_info = daily_work.groupby('Resource')['Time Spent (hrs)'].mean().sort_values(ascending=False)
            avg_all = overload_info.mean()
            overload_text = "\n".join([
                f"{res} averages {hrs:.1f} hrs/day; team average is {avg_all:.1f} hrs." + (" ⚠️ Overloaded" if hrs > avg_all * 1.5 else "")
                for res, hrs in overload_info.items()
            ])
            analytics_text += f"--- RESOURCE OVERLOAD ANALYSIS ---\n{overload_text}\n\n"
    
        if issues_df is not None and 'Due Date' in issues_df.columns and 'Start Date' in issues_df.columns:
            issues_df['Start Date'] = pd.to_datetime(issues_df['Start Date'], errors='coerce')
            issues_df['Due Date'] = pd.to_datetime(issues_df['Due Date'], errors='coerce')
            delayed = issues_df[issues_df['Due Date'] < pd.Timestamp.today()]
            gantt_delay_text = f"There are {len(delayed)} tasks past their due date.\n"
            analytics_text += f"--- GANTT DELAY ANALYSIS ---\n{gantt_delay_text}\n"
    
        if issues_df is not None and 'Status' in issues_df.columns:
            burnup_stats = issues_df['Status'].value_counts().to_string()
            analytics_text += f"--- BURNUP STATUS DISTRIBUTION ---\n{burnup_stats}\n"
    
    except Exception as e:
        st.error(f"Failed to summarize data: {e}")
        analytics_text = ""
    
    # Initialize OpenAI client
    # Direct API key setup
    api_key = st.secrets["OPENAI_API_KEY"]
    try:
        client = OpenAI(api_key=api_key)
    except Exception as e:
        st.error(f"Failed to initialize OpenAI client: {e}. API key issue detected.")
        return
        
    # ---------- Tab 1: Ask PM Buddy ----------
    with ai_tabs[0]:
        st.subheader("📋 Ask PM Buddy")
        
        # Role-based responses - new feature
        pm_roles = [
            "Project Manager",
            "Scrum Master",
            "Product Owner",
            "Team Lead",
            "Resource Manager",
            "Executive Sponsor",
            "Technical Lead"
        ]
        selected_role = st.selectbox("Select perspective:", pm_roles, index=0)
        
        # FAQ Dropdown
        faq_options = [
            "What are the current resource overload risks and how to mitigate them?",
            "Which tasks are at the highest risk of delay and why?",
            "How should we reallocate tasks to meet sprint deadlines?",
            "What recommendations do you have for balancing team workload this week?",
            "Which team members are underutilized and how can we better assign tasks to them?",
            "What is the forecast for project completion based on current progress?",
            "How many tasks are overdue and what action should be taken?",
            "Are there any skill gaps in the current sprint team?",
            "What happens if key resources become unavailable this week?",
            "How can we increase velocity without increasing burnout risk?"
        ]
        selected_faq = st.selectbox("Select a common question:", ["-- Select a question --"] + faq_options)
        if selected_faq != "-- Select a question --":
            st.session_state["selected_question"] = selected_faq
        
        sample_prompt = st.session_state.get("selected_question", "What are the key risks in current sprint and how can they be mitigated?")
        user_query = st.text_area("Ask AI PM Buddy a project-related question:", value=sample_prompt)
        
        # Persistent session chat memory
        if 'chat_session' not in st.session_state:
            st.session_state['chat_session'] = []
        
        if st.button("Ask AI PM Buddy"):
            if issues_df is None or worklogs_df is None:
                st.error("Please upload a valid JIRA Excel file or load the sample data first.")
                return
                
            with st.spinner("AI PM Buddy is thinking..."):
                try:
                    # Adding role-based perspective to the prompt
                    role_instructions = {
                        "Project Manager": "Focus on timeline, resource allocation, and overall project health.",
                        "Scrum Master": "Focus on team process, impediments, and sprint health metrics.",
                        "Product Owner": "Focus on value delivery, priorities, and feature completion.",
                        "Team Lead": "Focus on team capacity, technical implementation, and knowledge sharing.",
                        "Resource Manager": "Focus on resource utilization, skills management, and long-term staffing needs.",
                        "Executive Sponsor": "Focus on high-level overview, business impact, and strategic alignment.",
                        "Technical Lead": "Focus on technical dependencies, architecture concerns, and technical debt."
                    }
                    
                    prompt = f"""
    You are AI PM Buddy, a smart project management assistant. Answer as a {selected_role}. {role_instructions.get(selected_role, "")}
    Use the following structured summaries of JIRA project data and analytics to provide insights.
    
    --- ISSUE SUMMARY ---
    {issues_summary}
    
    --- WORKLOG SUMMARY (Hours per Resource) ---
    {worklog_summary}
    
    --- SKILL DISTRIBUTION ---
    {skill_distribution}
    
    --- LEAVE DISTRIBUTION ---
    {leave_summary}
    
    {analytics_text}
    User Query:
    {user_query}
    
    Answer:
    """
                    # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
                    # do not change this unless explicitly requested by the user
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": f"You are AI PM Buddy, a proactive assistant that gives insights, suggestions, alerts, and forecasts from the perspective of a {selected_role}."},
                            {"role": "user", "content": prompt}
                        ]
                    )
                    result = response.choices[0].message.content
                    st.success("✅ Response from AI PM Buddy")
                    st.markdown(result)
        
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    st.session_state['chat_session'].append({
                        "timestamp": timestamp,
                        "question": user_query,
                        "role": selected_role,
                        "answer": result
                    })
                except Exception as e:
                    st.error(f"AI PM Buddy failed to respond: {e}")
    
    # ---------- Tab 2: Smart PM Brief ----------
    with ai_tabs[1]:
        st.subheader("📋 Smart PM Brief")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("Generate a comprehensive PM brief with critical alerts, resource risks, and prioritized action items")
        with col2:
            brief_type = st.selectbox("Brief format:", ["Standard", "Detailed", "Executive"])
        
        if st.button("Generate Smart PM Brief"):
            if issues_df is None or worklogs_df is None:
                st.error("Please upload a valid JIRA Excel file or load the sample data first.")
                return
                
            with st.spinner("Generating smart brief with alerts and action items..."):
                try:
                    # Adjust prompt based on brief type
                    brief_instructions = {
                        "Standard": "Generate a balanced brief with equal focus on blockers, risks, and action items.",
                        "Detailed": "Generate a comprehensive and detailed brief with in-depth analysis and specific recommendations for each area of concern.",
                        "Executive": "Generate a concise executive summary focusing on high-level status, major risks, and strategic recommendations."
                    }
                    
                    brief_prompt = f"""
    Act as an AI project assistant. {brief_instructions.get(brief_type, "")} 
    Based on the following structured summaries and metrics, generate a smart PM brief with:
    • 🔴 Critical blockers
    • 🔶 Resource risks
    • 🟢 Green signals
    • 📋 Actionable recommendations
    
    Prioritize risk areas and provide actionable recommendations.
    
    --- ISSUE SUMMARY ---
    {issues_summary}
    
    --- WORKLOG SUMMARY ---
    {worklog_summary}
    
    --- SKILL DISTRIBUTION ---
    {skill_distribution}
    
    --- LEAVE DISTRIBUTION ---
    {leave_summary}
    
    {analytics_text}
    """
                    # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
                    # do not change this unless explicitly requested by the user
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "You are a proactive project management assistant that highlights risks, blockers, and gives actionable recommendations."},
                            {"role": "user", "content": brief_prompt}
                        ]
                    )
                    brief_result = response.choices[0].message.content
                    st.success("✅ Smart PM Brief generated")
                    st.markdown(brief_result)
                    
                    # Store in session for PDF export
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if 'generated_briefs' not in st.session_state:
                        st.session_state['generated_briefs'] = []
                    
                    st.session_state['generated_briefs'].append({
                        "timestamp": timestamp,
                        "type": brief_type,
                        "content": brief_result
                    })
                    
                    # Add PDF export option
                    from fpdf import FPDF
                    
                    class PDF(FPDF):
                        def header(self):
                            self.set_font('Arial', 'B', 12)
                            self.cell(0, 10, f'JIRA Project Management Brief - {brief_type}', 0, 1, 'C')
                            self.ln(5)
                            
                        def footer(self):
                            self.set_y(-15)
                            self.set_font('Arial', 'I', 8)
                            self.cell(0, 10, f'Generated by AI PM Buddy on {timestamp}', 0, 0, 'C')
                            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'R')
                    
                    def create_pdf(content, title):
                        # Create a simplified PDF generation approach
                        import io
                        from reportlab.lib.pagesizes import letter
                        from reportlab.lib import colors
                        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
                        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                        
                        # Clean content by removing problematic characters
                        import re
                        
                        # Replace emojis with plain text alternatives
                        content = content.replace('🔴', '[RED]')
                        content = content.replace('🟢', '[GREEN]')
                        content = content.replace('🔶', '[ORANGE]')
                        content = content.replace('📋', '[LIST]')
                        content = content.replace('•', '-')
                        
                        # Strip any other problematic characters
                        content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\xFF]', '', content)
                        
                        # Create BytesIO buffer and document
                        buffer = io.BytesIO()
                        doc = SimpleDocTemplate(buffer, pagesize=letter)
                        styles = getSampleStyleSheet()
                        story = []
                        
                        # Custom styles
                        title_style = ParagraphStyle(
                            'Title',
                            parent=styles['Title'],
                            fontSize=16,
                            spaceAfter=12
                        )
                        heading1_style = ParagraphStyle(
                            'Heading1',
                            parent=styles['Heading1'],
                            fontSize=14,
                            spaceAfter=8
                        )
                        heading2_style = ParagraphStyle(
                            'Heading2',
                            parent=styles['Heading2'],
                            fontSize=12,
                            spaceAfter=6
                        )
                        heading3_style = ParagraphStyle(
                            'Heading3', 
                            parent=styles['Heading3'],
                            fontSize=11,
                            spaceAfter=6
                        )
                        bold_style = ParagraphStyle(
                            'Bold',
                            parent=styles['Normal'],
                            fontSize=10,
                            spaceAfter=6,
                            fontName='Helvetica-Bold'
                        )
                        normal_style = ParagraphStyle(
                            'Normal',
                            parent=styles['Normal'],
                            fontSize=10,
                            spaceAfter=6
                        )
                        
                        # Add title
                        story.append(Paragraph(title, title_style))
                        story.append(Spacer(1, 12))
                        
                        # Add content with markdown parsing
                        for paragraph in content.split('\n\n'):
                            if not paragraph.strip():
                                continue
                                
                            # Handle Markdown-like formatting
                            paragraph = paragraph.strip()
                            
                            # Headings
                            if paragraph.startswith('# '):
                                story.append(Paragraph(paragraph[2:], heading1_style))
                            elif paragraph.startswith('## '):
                                story.append(Paragraph(paragraph[3:], heading2_style))
                            elif paragraph.startswith('### '):
                                # Check for special headings with emoji placeholders
                                if '[RED]' in paragraph:
                                    para_text = paragraph.replace('[RED]', '<font color="red">⬤</font>')
                                    story.append(Paragraph(para_text, heading3_style))
                                elif '[GREEN]' in paragraph:
                                    para_text = paragraph.replace('[GREEN]', '<font color="green">⬤</font>')
                                    story.append(Paragraph(para_text, heading3_style))
                                elif '[ORANGE]' in paragraph:
                                    para_text = paragraph.replace('[ORANGE]', '<font color="orange">⬤</font>')
                                    story.append(Paragraph(para_text, heading3_style))
                                elif '[LIST]' in paragraph:
                                    para_text = paragraph.replace('[LIST]', '📋')
                                    story.append(Paragraph(para_text, heading3_style))
                                else:
                                    story.append(Paragraph(paragraph[4:], heading3_style))
                            # Bold text paragraph
                            elif paragraph.startswith('**') and paragraph.endswith('**'):
                                story.append(Paragraph(paragraph[2:-2], bold_style))
                            # List items
                            elif paragraph.startswith('- ') or paragraph.startswith('* '):
                                lines = paragraph.split('\n')
                                bullet_text = ''
                                for line in lines:
                                    if line.startswith('- ') or line.startswith('* '):
                                        bullet_text += '• ' + line[2:] + '<br/>'
                                    else:
                                        bullet_text += line + '<br/>'
                                story.append(Paragraph(bullet_text, normal_style))
                            # Numbered list
                            elif paragraph.startswith('1. '):
                                lines = paragraph.split('\n')
                                numbered_text = ''
                                for i, line in enumerate(lines):
                                    if re.match(r'^\d+\.\s', line):
                                        num, text = line.split('. ', 1)
                                        numbered_text += f"{num}. {text}<br/>"
                                    else:
                                        numbered_text += line + '<br/>'
                                story.append(Paragraph(numbered_text, normal_style))
                            # Horizontal rule
                            elif paragraph == '---':
                                story.append(Paragraph("<hr width='100%'/>", normal_style))
                            # Regular paragraph with potential inline formatting
                            else:
                                # Handle inline bold with **text**
                                result = paragraph
                                bold_pattern = r'\*\*(.*?)\*\*'
                                result = re.sub(bold_pattern, r'<b>\1</b>', result)
                                
                                # Handle line breaks
                                result = result.replace('\n', '<br/>')
                                
                                story.append(Paragraph(result, normal_style))
                            
                            story.append(Spacer(1, 6))
                        
                        # Build document
                        doc.build(story)
                        buffer.seek(0)
                        return buffer.getvalue()
                    
                    # Generate the PDF
                    try:
                        pdf_content = create_pdf(brief_result, f"Smart PM Brief ({brief_type}) - {timestamp}")
                        st.download_button(
                            label="📥 Download as PDF",
                            data=pdf_content,
                            file_name=f"PM_Brief_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf"
                        )
                    except Exception as pdf_err:
                        st.warning(f"Could not generate PDF: {pdf_err}. Download as text instead.")
                        st.download_button(
                            label="📥 Download as Text",
                            data=brief_result,
                            file_name=f"PM_Brief_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                        )
                        
                except Exception as e:
                    st.error(f"GPT Smart Brief failed: {e}")
    
    # ---------- Tab 3: What-if Simulation ----------
    with ai_tabs[2]:
        st.subheader("🔮 What-if Simulation")
        
        # Enhanced simulation options
        simulation_type = st.radio(
            "Simulation type:",
            ["Resource Unavailability", "Schedule Delay", "Scope Change"],
            horizontal=True
        )
        
        if simulation_type == "Resource Unavailability":
            if worklogs_df is not None and issues_df is not None:
                resource_list = sorted(set(worklogs_df['Resource'].dropna().unique()).union(set(issues_df['Assignee'].dropna().unique())))
                unavailable_selection = st.multiselect("Select resources to simulate unavailability:", resource_list)
                
                duration_options = ["1 day", "3 days", "1 week", "2 weeks", "1 month"]
                unavailable_duration = st.selectbox("Duration of unavailability:", duration_options)
                
                if st.button("Simulate Impact") and unavailable_selection:
                    impacted_worklogs = worklogs_df[worklogs_df['Resource'].isin(unavailable_selection)]
                    impacted_issues = issues_df[issues_df['Assignee'].isin(unavailable_selection)]
            
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("### 📊 Impacted Worklogs")
                        st.dataframe(impacted_worklogs)
            
                    with col2:
                        st.markdown("### 📋 Impacted Issues")
                        st.dataframe(impacted_issues)
            
                    impact_prompt = f"""
            Act as a project management assistant. Based on the following scenario, simulate the impact of these resources being unavailable for {unavailable_duration}: {', '.join(unavailable_selection)}
            
            --- IMPACTED WORKLOGS ---
            {impacted_worklogs.to_string(index=False)}
            
            --- IMPACTED ISSUES ---
            {impacted_issues.to_string(index=False)}
            
            --- PROJECT CONTEXT ---
            {analytics_text}
            
            Analyze and provide:
            1. A risk summary with severity levels (High, Medium, Low)
            2. Timeline impact assessment
            3. Detailed mitigation plan with specific task reassignments
            4. Recommendations for process improvements
            """
                    with st.spinner("Analyzing what-if scenario with AI PM Buddy..."):
                        try:
                            # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
                            # do not change this unless explicitly requested by the user
                            response = client.chat.completions.create(
                                model="gpt-4o",
                                messages=[
                                    {"role": "system", "content": "You are a project management AI that performs detailed what-if impact analysis and gives specific risk mitigation advice with concrete recommendations."},
                                    {"role": "user", "content": impact_prompt}
                                ]
                            )
                            result = response.choices[0].message.content
                            st.success("✅ Simulation Analysis Ready")
                            st.markdown(result)
                            
                            # Store simulation results
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            if 'simulation_history' not in st.session_state:
                                st.session_state['simulation_history'] = []
                            
                            st.session_state['simulation_history'].append({
                                "timestamp": timestamp,
                                "type": "Resource Unavailability",
                                "resources": unavailable_selection,
                                "duration": unavailable_duration,
                                "result": result
                            })
                            
                            # Convert the simulation to PDF format
                            try:
                                # Create a PDF report
                                import io
                                from reportlab.lib.pagesizes import letter
                                from reportlab.lib import colors
                                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                                
                                # Create BytesIO buffer and document
                                buffer = io.BytesIO()
                                doc = SimpleDocTemplate(buffer, pagesize=letter)
                                styles = getSampleStyleSheet()
                                story = []
                                
                                # Custom styles
                                title_style = ParagraphStyle(
                                    'Title',
                                    parent=styles['Title'],
                                    fontSize=16,
                                    spaceAfter=12
                                )
                                heading_style = ParagraphStyle(
                                    'Heading',
                                    parent=styles['Heading2'],
                                    fontSize=12,
                                    spaceAfter=6
                                )
                                normal_style = ParagraphStyle(
                                    'Body',
                                    parent=styles['Normal'],
                                    fontSize=10,
                                    spaceAfter=6
                                )
                                
                                # Add title & header info
                                story.append(Paragraph("Resource Unavailability Simulation", title_style))
                                story.append(Spacer(1, 12))
                                
                                story.append(Paragraph(f"<b>Resources:</b> {', '.join(unavailable_selection)}", normal_style))
                                story.append(Paragraph(f"<b>Duration:</b> {unavailable_duration}", normal_style))
                                story.append(Paragraph(f"<b>Date:</b> {timestamp}", normal_style))
                                story.append(Spacer(1, 12))
                                
                                # Process markdown-like content for better formatting
                                # Create styles for different heading levels and formatting
                                heading1_style = ParagraphStyle(
                                    'Heading1',
                                    parent=styles['Heading1'],
                                    fontSize=14,
                                    spaceAfter=8
                                )
                                heading2_style = ParagraphStyle(
                                    'Heading2',
                                    parent=styles['Heading2'],
                                    fontSize=12,
                                    spaceAfter=6
                                )
                                heading3_style = ParagraphStyle(
                                    'Heading3', 
                                    parent=styles['Heading3'],
                                    fontSize=11,
                                    spaceAfter=6
                                )
                                bold_style = ParagraphStyle(
                                    'Bold',
                                    parent=styles['Normal'],
                                    fontSize=10,
                                    spaceAfter=6,
                                    fontName='Helvetica-Bold'
                                )
                                
                                # Process content with markdown-like formatting
                                for paragraph in result.split('\n\n'):
                                    if not paragraph.strip():
                                        continue
                                        
                                    # Replace markdown with HTML formatting
                                    paragraph = paragraph.strip()
                                    
                                    # Handle different formats
                                    if paragraph.startswith('# '):
                                        story.append(Paragraph(paragraph[2:], heading1_style))
                                    elif paragraph.startswith('## '):
                                        story.append(Paragraph(paragraph[3:], heading2_style))
                                    elif paragraph.startswith('### '):
                                        story.append(Paragraph(paragraph[4:], heading3_style))
                                    elif paragraph.startswith('**') and paragraph.endswith('**'):
                                        story.append(Paragraph(paragraph[2:-2], bold_style))
                                    elif '**' in paragraph or '__' in paragraph:
                                        # Replace inline bold formatting
                                        import re
                                        formatted = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', paragraph)
                                        formatted = re.sub(r'__(.*?)__', r'<b>\1</b>', formatted)
                                        formatted = formatted.replace('\n', '<br/>')
                                        story.append(Paragraph(formatted, normal_style))
                                    elif paragraph.startswith('- ') or paragraph.startswith('* '):
                                        # Bullet points
                                        lines = paragraph.split('\n')
                                        bullet_text = ''
                                        for line in lines:
                                            if line.startswith('- ') or line.startswith('* '):
                                                bullet_text += '• ' + line[2:] + '<br/>'
                                            else:
                                                bullet_text += line + '<br/>'
                                        story.append(Paragraph(bullet_text, normal_style))
                                    elif paragraph.strip().startswith('1. '):
                                        # Numbered list
                                        lines = paragraph.split('\n')
                                        numbered_text = ''
                                        for line in lines:
                                            if re.match(r'^\d+\.\s', line.strip()):
                                                parts = line.strip().split('. ', 1)
                                                if len(parts) > 1:
                                                    numbered_text += parts[0] + '. ' + parts[1] + '<br/>'
                                            else:
                                                numbered_text += line + '<br/>'
                                        story.append(Paragraph(numbered_text, normal_style))
                                    else:
                                        # Regular paragraph
                                        story.append(Paragraph(paragraph.replace('\n', '<br/>'), normal_style))
                                    
                                    story.append(Spacer(1, 6))
                                
                                # Build document
                                doc.build(story)
                                buffer.seek(0)
                                pdf_content = buffer.getvalue()
                                
                                # Add download button for PDF
                                st.download_button(
                                    label="📥 Download Simulation Report (PDF)",
                                    data=pdf_content,
                                    file_name=f"Simulation_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                                    mime="application/pdf"
                                )
                            except Exception as pdf_err:
                                st.warning(f"Could not generate PDF: {pdf_err}. Download as text instead.")
                                st.download_button(
                                    label="📥 Download Simulation Report (Text)",
                                    data=f"# Resource Unavailability Simulation\nResources: {', '.join(unavailable_selection)}\nDuration: {unavailable_duration}\nDate: {timestamp}\n\n{result}",
                                    file_name=f"Simulation_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                                )
                            
                        except Exception as e:
                            st.error(f"GPT Simulation failed: {e}")
                            
        elif simulation_type == "Schedule Delay":
            st.info("This feature allows you to simulate the impact of delays in key milestones or deliverables.")
            delay_options = ["Sprint delay", "Milestone delay", "Release delay"]
            delay_type = st.selectbox("Type of delay:", delay_options)
            delay_duration = st.slider("Delay duration (days):", 1, 30, 5)
            
            if st.button("Simulate Schedule Delay") and issues_df is not None:
                with st.spinner("Analyzing schedule delay impact..."):
                    # Calculate affected issues based on delay type
                    current_date = pd.Timestamp.today()
                    delay_end_date = current_date + pd.Timedelta(days=delay_duration)
                    
                    # Create different scenarios based on delay type
                    if delay_type == "Sprint delay":
                        # Assume current sprint issues will be delayed
                        affected_issues = issues_df[issues_df['Due Date'].between(current_date, current_date + pd.Timedelta(days=14))]
                        delay_context = f"a sprint delay of {delay_duration} days"
                    elif delay_type == "Milestone delay":
                        # Assume milestone issues (with higher priority) will be delayed
                        affected_issues = issues_df[(issues_df['Priority'] == 'High') | (issues_df['Priority'] == 'Highest')]
                        delay_context = f"a milestone delay of {delay_duration} days affecting high priority items"
                    else:  # Release delay
                        # Assume all issues with due dates in next 30 days will be delayed
                        affected_issues = issues_df[issues_df['Due Date'].between(current_date, current_date + pd.Timedelta(days=30))]
                        delay_context = f"a release delay of {delay_duration} days"
                    
                    # Show affected issues
                    st.subheader(f"Affected Issues for {delay_type}")
                    st.dataframe(affected_issues)
                    
                    # Prepare prompt for AI analysis
                    delay_prompt = f"""
                Act as a project management assistant. Based on the following scenario, simulate the impact of {delay_context}.
                
                --- AFFECTED ISSUES ---
                {affected_issues.to_string(index=False)}
                
                --- PROJECT CONTEXT ---
                {analytics_text}
                
                Analyze and provide:
                1. Critical impact assessment on project timeline, dependencies, and costs
                2. Team impact analysis (overtime needs, resource challenges, morale)
                3. Detailed mitigation strategies with specific recommendations
                4. Stakeholder communication plan with key messages
                5. Recommendations for process improvements to avoid similar delays
                """
                    
                    try:
                        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
                        # do not change this unless explicitly requested by the user
                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": "You are a project management AI specialized in schedule impact analysis and mitigation planning."},
                                {"role": "user", "content": delay_prompt}
                            ]
                        )
                        result = response.choices[0].message.content
                        st.success("✅ Schedule Delay Analysis Complete")
                        st.markdown(result)
                        
                        # Store simulation results
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        if 'simulation_history' not in st.session_state:
                            st.session_state['simulation_history'] = []
                        
                        st.session_state['simulation_history'].append({
                            "timestamp": timestamp,
                            "type": "Schedule Delay",
                            "delay_type": delay_type,
                            "duration": f"{delay_duration} days",
                            "result": result,
                            "resources": ["Schedule"] # Just for compatibility with existing history structure
                        })
                        
                        # Create PDF for download
                        try:
                            # Create a PDF report
                            import io
                            from reportlab.lib.pagesizes import letter
                            from reportlab.lib import colors
                            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                            
                            # Create BytesIO buffer and document
                            buffer = io.BytesIO()
                            doc = SimpleDocTemplate(buffer, pagesize=letter)
                            styles = getSampleStyleSheet()
                            story = []
                            
                            # Custom styles
                            title_style = ParagraphStyle(
                                'Title',
                                parent=styles['Title'],
                                fontSize=16,
                                spaceAfter=12
                            )
                            normal_style = ParagraphStyle(
                                'Body',
                                parent=styles['Normal'],
                                fontSize=10,
                                spaceAfter=6
                            )
                            
                            # Add title & header info
                            story.append(Paragraph(f"Schedule Delay Simulation: {delay_type}", title_style))
                            story.append(Spacer(1, 12))
                            
                            story.append(Paragraph(f"<b>Delay Type:</b> {delay_type}", normal_style))
                            story.append(Paragraph(f"<b>Duration:</b> {delay_duration} days", normal_style))
                            story.append(Paragraph(f"<b>Date:</b> {timestamp}", normal_style))
                            story.append(Spacer(1, 12))
                            
                            # Add content by paragraphs
                            for paragraph in result.split('\n\n'):
                                if paragraph.strip():
                                    story.append(Paragraph(paragraph.replace('\n', '<br/>'), normal_style))
                                    story.append(Spacer(1, 6))
                            
                            # Build document
                            doc.build(story)
                            buffer.seek(0)
                            pdf_content = buffer.getvalue()
                            
                            # Add download button for PDF
                            st.download_button(
                                label="📥 Download Schedule Delay Analysis (PDF)",
                                data=pdf_content,
                                file_name=f"Schedule_Delay_Simulation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                                mime="application/pdf"
                            )
                        except Exception as pdf_err:
                            st.warning(f"Could not generate PDF: {pdf_err}. Download as text instead.")
                            st.download_button(
                                label="📥 Download Schedule Delay Analysis (Text)",
                                data=f"# Schedule Delay Simulation: {delay_type}\nDuration: {delay_duration} days\nDate: {timestamp}\n\n{result}",
                                file_name=f"Schedule_Delay_Simulation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                            )
                    except Exception as e:
                        st.error(f"Schedule Delay Simulation failed: {e}")
                
        elif simulation_type == "Scope Change":
            st.info("This feature allows you to simulate the impact of adding or removing stories/features.")
            scope_change = st.radio("Scope change type:", ["Add stories", "Remove stories"])
            story_points = st.number_input("Story points to add/remove:", min_value=1, max_value=100, value=10)
            
            if st.button("Simulate Scope Change") and issues_df is not None:
                with st.spinner("Analyzing scope change impact..."):
                    # Get current team capacity
                    if worklogs_df is not None:
                        team_capacity = worklogs_df.groupby('Resource')['Time Spent (hrs)'].sum().reset_index()
                        avg_hours_per_point = 8  # Assumption: 1 story point = 8 hours of work
                        total_hours_change = story_points * avg_hours_per_point
                        
                        # Show scope change visualization
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Create a bar chart showing current capacity vs new scope
                            current_scope = issues_df['Story Points'].sum() if 'Story Points' in issues_df.columns else len(issues_df) * 3  # Estimate if no story points
                            
                            if scope_change == "Add stories":
                                new_scope = current_scope + story_points
                                change_type = "increase"
                            else:  # Remove stories
                                new_scope = max(0, current_scope - story_points)
                                change_type = "decrease"
                            
                            # Create comparison chart
                            scope_data = pd.DataFrame({
                                'Status': ['Current Scope', 'New Scope'],
                                'Story Points': [current_scope, new_scope]
                            })
                            
                            scope_fig = px.bar(
                                scope_data, 
                                x='Status', 
                                y='Story Points',
                                title=f"Scope {change_type} of {story_points} points",
                                color='Status',
                                color_discrete_map={'Current Scope': 'blue', 'New Scope': 'red' if scope_change == "Add stories" else 'green'}
                            )
                            st.plotly_chart(scope_fig, use_container_width=True)
                        
                        with col2:
                            # Impact on timeline
                            velocity = issues_df[issues_df['Status'] == 'Done'].shape[0] / 2 if 'Status' in issues_df.columns else 5  # Assume 2-week sprints
                            current_timeline_sprints = current_scope / velocity if velocity > 0 else 0
                            new_timeline_sprints = new_scope / velocity if velocity > 0 else 0
                            
                            # Create timeline impact visualization
                            timeline_data = pd.DataFrame({
                                'Timeline': ['Current (sprints)', 'New (sprints)'],
                                'Sprints': [current_timeline_sprints, new_timeline_sprints]
                            })
                            
                            timeline_fig = px.bar(
                                timeline_data, 
                                x='Timeline', 
                                y='Sprints',
                                title="Timeline Impact (in sprints)",
                                color='Timeline',
                                color_discrete_map={'Current (sprints)': 'blue', 'New (sprints)': 'red' if scope_change == "Add stories" else 'green'}
                            )
                            st.plotly_chart(timeline_fig, use_container_width=True)
                    
                    # Prepare prompt for AI analysis based on scope change
                    scope_prompt = f"""
                Act as a project management assistant. Based on the following scenario, simulate the impact of {scope_change.lower()} with {story_points} story points.
                
                --- PROJECT DATA ---
                Current number of issues: {len(issues_df)}
                Current scope in story points: {issues_df['Story Points'].sum() if 'Story Points' in issues_df.columns else len(issues_df) * 3}
                Average hours per story point: {avg_hours_per_point}
                Total hours change: {total_hours_change}
                
                --- PROJECT CONTEXT ---
                {analytics_text}
                
                Analyze and provide:
                1. Timeline impact assessment (how delivery dates will change)
                2. Resource impact analysis (who will be most affected, capacity issues)
                3. Quality and risk implications
                4. Budget impact 
                5. Detailed recommendations for handling this scope change
                6. Communication strategy for stakeholders
                """
                    
                    try:
                        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
                        # do not change this unless explicitly requested by the user
                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": "You are a project management AI specialized in scope change impact analysis and mitigation planning."},
                                {"role": "user", "content": scope_prompt}
                            ]
                        )
                        result = response.choices[0].message.content
                        st.success("✅ Scope Change Analysis Complete")
                        st.markdown(result)
                        
                        # Store simulation results
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        if 'simulation_history' not in st.session_state:
                            st.session_state['simulation_history'] = []
                        
                        st.session_state['simulation_history'].append({
                            "timestamp": timestamp,
                            "type": "Scope Change",
                            "delay_type": scope_change,  # Reusing the field for compatibility
                            "duration": f"{story_points} points",
                            "result": result,
                            "resources": ["Scope"]  # For compatibility with existing structure
                        })
                        
                        # Create PDF for download
                        try:
                            # Create a PDF report
                            import io
                            from reportlab.lib.pagesizes import letter
                            from reportlab.lib import colors
                            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                            
                            # Create BytesIO buffer and document
                            buffer = io.BytesIO()
                            doc = SimpleDocTemplate(buffer, pagesize=letter)
                            styles = getSampleStyleSheet()
                            story = []
                            
                            # Custom styles
                            title_style = ParagraphStyle(
                                'Title',
                                parent=styles['Title'],
                                fontSize=16,
                                spaceAfter=12
                            )
                            normal_style = ParagraphStyle(
                                'Body',
                                parent=styles['Normal'],
                                fontSize=10,
                                spaceAfter=6
                            )
                            
                            # Add title & header info
                            story.append(Paragraph(f"Scope Change Simulation: {scope_change}", title_style))
                            story.append(Spacer(1, 12))
                            
                            story.append(Paragraph(f"<b>Change Type:</b> {scope_change}", normal_style))
                            story.append(Paragraph(f"<b>Story Points:</b> {story_points}", normal_style))
                            story.append(Paragraph(f"<b>Date:</b> {timestamp}", normal_style))
                            story.append(Spacer(1, 12))
                            
                            # Add content by paragraphs
                            for paragraph in result.split('\n\n'):
                                if paragraph.strip():
                                    story.append(Paragraph(paragraph.replace('\n', '<br/>'), normal_style))
                                    story.append(Spacer(1, 6))
                            
                            # Build document
                            doc.build(story)
                            buffer.seek(0)
                            pdf_content = buffer.getvalue()
                            
                            # Add download button for PDF
                            st.download_button(
                                label="📥 Download Scope Change Analysis (PDF)",
                                data=pdf_content,
                                file_name=f"Scope_Change_Simulation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                                mime="application/pdf"
                            )
                        except Exception as pdf_err:
                            st.warning(f"Could not generate PDF: {pdf_err}. Download as text instead.")
                            st.download_button(
                                label="📥 Download Scope Change Analysis (Text)",
                                data=f"# Scope Change Simulation: {scope_change}\nStory Points: {story_points}\nDate: {timestamp}\n\n{result}",
                                file_name=f"Scope_Change_Simulation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                            )
                    except Exception as e:
                        st.error(f"Scope Change Simulation failed: {e}")
    
    # ---------- Tab 4: Load Redistribution Planning ----------
    with ai_tabs[3]:
        st.subheader("📊 Load Redistribution Planning")
        
        planning_col1, planning_col2 = st.columns([2, 1])
        with planning_col1:
            st.markdown("Optimize workload distribution across team members and identify opportunities for better resource allocation")
        with planning_col2:
            timeframe = st.selectbox("Planning timeframe:", ["Current Sprint", "Next Sprint", "Next Month", "Next Quarter"])
            
        if st.button("Generate Load Redistribution Plan"):
            if worklogs_df is None or issues_df is None:
                st.error("Please upload a valid JIRA Excel file or load the sample data first.")
                return
                
            with st.spinner("Analyzing workloads and forecasting load balancing..."):
                try:
                    forecast_text = ""
                    if worklogs_df is not None:
                        worklogs_df['Date'] = pd.to_datetime(worklogs_df['Date'], errors='coerce')
                        worklogs_df = worklogs_df.dropna(subset=['Date'])
                        worklogs_df['Week'] = worklogs_df['Date'].dt.strftime('%Y-%U')
                        weekly_load = worklogs_df.groupby(['Week', 'Resource'])['Time Spent (hrs)'].sum().reset_index()
                        weekly_pivot = weekly_load.pivot(index='Resource', columns='Week', values='Time Spent (hrs)').fillna(0)
                        
                        # Display the weekly load matrix as a heatmap
                        st.subheader("Weekly Load Matrix")
                        
                        # Generate a heatmap visualization using Plotly
                        load_fig = px.imshow(
                            weekly_pivot,
                            labels=dict(x="Week", y="Resource", color="Hours"),
                            x=weekly_pivot.columns,
                            y=weekly_pivot.index,
                            color_continuous_scale='viridis',
                            title="Resource Weekly Load Heatmap"
                        )
                        load_fig.update_layout(height=400)
                        st.plotly_chart(load_fig, use_container_width=True)
                        
                        # Also add the text representation for AI analysis
                        forecast_text += f"--- WEEKLY LOAD MATRIX ---\n{weekly_pivot.to_string()}\n\n"
        
                    # Calculate and display average productivity by resource
                    avg_productivity = worklogs_df.groupby('Resource')['Time Spent (hrs)'].mean()
                    
                    # Create bar chart for average productivity
                    productivity_fig = px.bar(
                        x=avg_productivity.index, 
                        y=avg_productivity.values,
                        labels={'x':'Resource', 'y':'Avg. Hours/Day'},
                        title="Average Daily Productivity by Resource",
                        color=avg_productivity.values,
                        color_continuous_scale='RdYlGn_r'
                    )
                    st.plotly_chart(productivity_fig, use_container_width=True)
                    
                    forecast_text += f"--- AVERAGE PRODUCTIVITY ---\n{avg_productivity.to_string()}\n\n"
        
                    # Calculate overdue tasks
                    overdue_issues = issues_df[issues_df['Due Date'] < pd.Timestamp.today()] if issues_df is not None else pd.DataFrame()
                    if not overdue_issues.empty and 'Assignee' in overdue_issues.columns:
                        overdue_count = overdue_issues['Assignee'].value_counts()
                        
                        # Display overdue tasks by assignee
                        st.subheader("Overdue Tasks by Assignee")
                        overdue_fig = px.pie(
                            names=overdue_count.index,
                            values=overdue_count.values,
                            title=f"Distribution of {len(overdue_issues)} Overdue Tasks"
                        )
                        st.plotly_chart(overdue_fig, use_container_width=True)
                    
                    forecast_text += f"--- OVERDUE TASKS ---\n{len(overdue_issues)} overdue tasks"    
                    if not overdue_issues.empty and 'Assignee' in overdue_issues.columns:
                        forecast_text += f"\n{overdue_issues['Assignee'].value_counts().to_string()}\n\n"
                    else:
                        forecast_text += "\n\n"
        
                    # Get skill distribution for better allocation
                    if skills_df is not None:
                        skill_matrix = pd.crosstab(skills_df['Resource'], skills_df['Skillset'])
                        forecast_text += f"--- SKILL MATRIX ---\n{skill_matrix.to_string()}\n\n"
        
                    redistribution_prompt = f"""
            You are a project optimization assistant for {timeframe}. Based on the following project metrics:
            1. Weekly load matrix showing each resource's hours over time
            2. Average productivity by resource
            3. Overdue tasks distribution
            4. Skill matrix for resource capabilities
            
            Provide a comprehensive redistribution plan with:
            1. Specific task reassignments (which resources should take over which tasks)
            2. Weekly hour targets for each team member 
            3. Prioritization guidance for overloaded resources
            4. Utilization improvements for underutilized resources
            5. Skill-based allocation recommendations
            
            {forecast_text}
            """
                    # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
                    # do not change this unless explicitly requested by the user
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "You are a resource planner that creates smart load balancing and forecasting plans for project teams. Provide specific, actionable recommendations."},
                            {"role": "user", "content": redistribution_prompt}
                        ]
                    )
                    result = response.choices[0].message.content
                    st.success("✅ Load Redistribution Plan Ready")
                    
                    # Display the result with better formatting
                    st.subheader("AI-Generated Redistribution Plan")
                    st.markdown(result)
        
                    # Store in session for retrieval
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if 'redistribution_plans' not in st.session_state:
                        st.session_state['redistribution_plans'] = []
                    st.session_state['redistribution_plans'].append({
                        "timestamp": timestamp,
                        "timeframe": timeframe,
                        "content": result
                    })
                    
                    # Add PDF download for Load Plan
                    try:
                        # Create a PDF report
                        import io
                        from reportlab.lib.pagesizes import letter
                        from reportlab.lib import colors
                        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                        
                        # Create BytesIO buffer and document
                        buffer = io.BytesIO()
                        doc = SimpleDocTemplate(buffer, pagesize=letter)
                        styles = getSampleStyleSheet()
                        story = []
                        
                        # Custom styles
                        title_style = ParagraphStyle(
                            'Title',
                            parent=styles['Title'],
                            fontSize=16,
                            spaceAfter=12
                        )
                        heading_style = ParagraphStyle(
                            'Heading',
                            parent=styles['Heading2'],
                            fontSize=12,
                            spaceAfter=6
                        )
                        normal_style = ParagraphStyle(
                            'Body',
                            parent=styles['Normal'],
                            fontSize=10,
                            spaceAfter=6
                        )
                        
                        # Add title & header info
                        story.append(Paragraph(f"{timeframe} Load Redistribution Plan", title_style))
                        story.append(Spacer(1, 12))
                        story.append(Paragraph(f"<b>Generated:</b> {timestamp}", normal_style))
                        story.append(Spacer(1, 12))
                        
                        # Add content by paragraphs
                        for paragraph in result.split('\n\n'):
                            if paragraph.strip():
                                story.append(Paragraph(paragraph.replace('\n', '<br/>'), normal_style))
                                story.append(Spacer(1, 6))
                        
                        # Build document
                        doc.build(story)
                        buffer.seek(0)
                        pdf_content = buffer.getvalue()
                        
                        # Add download button for PDF
                        st.download_button(
                            label="📥 Download Redistribution Plan (PDF)",
                            data=pdf_content,
                            file_name=f"Load_Plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf"
                        )
                    except Exception as pdf_err:
                        st.warning(f"Could not generate PDF: {pdf_err}. Download as text instead.")
                        st.download_button(
                            label="📥 Download Redistribution Plan (Text)",
                            data=f"# {timeframe} Load Redistribution Plan\nGenerated: {timestamp}\n\n{result}",
                            file_name=f"Load_Plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                        )
                    
                except Exception as e:
                    st.error(f"Load Redistribution Planning failed: {e}")
                    st.exception(e)

    # ---------- Tab 5: Conversation History ----------
    with ai_tabs[4]:
        st.subheader("💬 Conversation History")
        
        # Tabs for different types of history
        history_tabs = st.tabs(["Questions & Answers", "Smart Briefs", "Simulations", "Redistribution Plans"])
        
        # Tab 1: Questions & Answers History
        with history_tabs[0]:
            if st.session_state.get('chat_session'):
                # Add export option
                st.download_button(
                    label="📥 Export All Conversations as Text",
                    data="\n\n".join([f"Q ({chat['timestamp']} as {chat.get('role', 'Project Manager')}): {chat['question']}\n\nA: {chat['answer']}\n\n---------------" 
                                    for chat in st.session_state['chat_session']]),
                    file_name=f"PM_Buddy_Conversations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                )
                
                # Option to generate a PDF of all conversations
                if st.button("Export All Conversations as PDF"):
                    try:
                        from fpdf import FPDF
                        
                        class PDF(FPDF):
                            def header(self):
                                self.set_font('Arial', 'B', 12)
                                self.cell(0, 10, f'AI PM Buddy Conversation History', 0, 1, 'C')
                                self.ln(5)
                                
                            def footer(self):
                                self.set_y(-15)
                                self.set_font('Arial', 'I', 8)
                                self.cell(0, 10, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 0, 'C')
                                self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'R')
                        
                        def create_pdf(chats):
                            # Use ReportLab for PDF generation (more robust than FPDF)
                            import io
                            from reportlab.lib.pagesizes import letter
                            from reportlab.lib import colors
                            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
                            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                            
                            # Create BytesIO buffer and document
                            buffer = io.BytesIO()
                            doc = SimpleDocTemplate(buffer, pagesize=letter)
                            styles = getSampleStyleSheet()
                            story = []
                            
                            # Custom styles
                            title_style = ParagraphStyle(
                                'Title',
                                parent=styles['Title'],
                                fontSize=16,
                                spaceAfter=12
                            )
                            heading_style = ParagraphStyle(
                                'Heading',
                                parent=styles['Heading2'],
                                fontSize=12,
                                spaceAfter=6
                            )
                            normal_style = ParagraphStyle(
                                'Body',
                                parent=styles['Normal'],
                                fontSize=10,
                                spaceAfter=6
                            )
                            
                            # Add title
                            story.append(Paragraph("AI PM Buddy - Conversation History", title_style))
                            story.append(Spacer(1, 12))
                            
                            # Clean text function
                            def clean_text(text):
                                if not text:
                                    return ""
                                # Replace problematic characters
                                text = text.replace('🔴', '[RED]').replace('🟢', '[GREEN]')
                                text = text.replace('🔶', '[ORANGE]').replace('📋', '[LIST]')
                                text = text.replace('•', '-').replace('\n', '<br/>')
                                # Strip any other problematic characters
                                import re
                                text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\xFF]', '', text)
                                return text
                            
                            # Process each conversation
                            for idx, chat in enumerate(chats):
                                # Question section
                                question_header = f"Q ({chat['timestamp']} as {chat.get('role', 'Project Manager')}):"
                                story.append(Paragraph(question_header, heading_style))
                                story.append(Paragraph(clean_text(chat.get('question', '')), normal_style))
                                story.append(Spacer(1, 6))
                                
                                # Answer section
                                story.append(Paragraph("A:", heading_style))
                                story.append(Paragraph(clean_text(chat.get('answer', '')), normal_style))
                                
                                # Add separator unless it's the last item
                                if idx < len(chats) - 1:
                                    story.append(Spacer(1, 12))
                                    story.append(Paragraph("---------------------------------------------", normal_style))
                                    story.append(Spacer(1, 12))
                            
                            # Build document
                            doc.build(story)
                            buffer.seek(0)
                            return buffer.getvalue()
                        
                        # Generate the PDF
                        try:
                            pdf_content = create_pdf(st.session_state['chat_session'])
                            st.download_button(
                                label="📥 Download PDF",
                                data=pdf_content,
                                file_name=f"PM_Buddy_Conversations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                                mime="application/pdf"
                            )
                        except Exception as pdf_err:
                            st.warning(f"Could not generate PDF: {pdf_err}. Using text export instead.")
                    except Exception as e:
                        st.error(f"Failed to generate PDF: {e}")
                
                # Display the history
                for idx, chat in enumerate(st.session_state['chat_session']):
                    with st.expander(f"Q: {chat['question'][:50]}{'...' if len(chat['question']) > 50 else ''}", expanded=idx==0):
                        st.markdown(f"**Asked at:** {chat['timestamp']}")
                        st.markdown(f"**Perspective:** {chat.get('role', 'Project Manager')}")
                        st.markdown(f"**Question:** {chat['question']}")
                        st.markdown(f"**Answer:** {chat['answer']}")
            else:
                st.info("No conversation history yet. Start asking questions in the 'Ask PM Buddy' tab.")
                
        # Tab 2: Smart Briefs History
        with history_tabs[1]:
            if st.session_state.get('generated_briefs'):
                for idx, brief in enumerate(st.session_state['generated_briefs']):
                    with st.expander(f"{brief['type']} Brief - {brief['timestamp']}", expanded=idx==0):
                        st.markdown(brief['content'])
                        
                        # Add download option for individual briefs
                        st.download_button(
                            label="📥 Download this Brief",
                            data=f"# {brief['type']} PM Brief\nGenerated: {brief['timestamp']}\n\n{brief['content']}",
                            file_name=f"PM_Brief_{brief['type']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                        )
            else:
                st.info("No smart briefs generated yet. Generate briefs in the 'Smart PM Brief' tab.")
                
        # Tab 3: Simulations History
        with history_tabs[2]:
            if st.session_state.get('simulation_history'):
                for idx, sim in enumerate(st.session_state['simulation_history']):
                    with st.expander(f"{sim['type']} - {', '.join(sim['resources'][:3])}{' and more' if len(sim['resources']) > 3 else ''} - {sim['timestamp']}", expanded=idx==0):
                        st.markdown(f"**Simulation Type:** {sim['type']}")
                        st.markdown(f"**Resources:** {', '.join(sim['resources'])}")
                        st.markdown(f"**Duration:** {sim['duration']}")
                        st.markdown(f"**Generated at:** {sim['timestamp']}")
                        st.markdown("**Results:**")
                        st.markdown(sim['result'])
            else:
                st.info("No simulations run yet. Run simulations in the 'What-if Simulation' tab.")
                
        # Tab 4: Redistribution Plans History
        with history_tabs[3]:
            if st.session_state.get('redistribution_plans'):
                for idx, plan in enumerate(st.session_state['redistribution_plans']):
                    with st.expander(f"{plan['timeframe']} Plan - {plan['timestamp']}", expanded=idx==0):
                        st.markdown(f"**Timeframe:** {plan['timeframe']}")
                        st.markdown(f"**Generated at:** {plan['timestamp']}")
                        st.markdown("**Plan:**")
                        st.markdown(plan['content'])
            else:
                st.info("No redistribution plans generated yet. Generate plans in the 'Load Planning' tab.")

# ---------- Main app navigation ----------
if nav_selection == "📊 Dashboard":
    dashboard()
elif nav_selection == "📅 Gantt Chart":
    gantt_chart()
elif nav_selection == "🚦 Traffic Light Matrix":
    traffic_light_matrix()
elif nav_selection == "📈 Sprint Burnup":
    sprint_burnup()
elif nav_selection == "📋 PM Daily Brief":
    pm_daily_brief()
elif nav_selection == "📡 Radar Chart":
    radar_chart()
elif nav_selection == "🫧 Bubble Chart":
    bubble_chart_overload_velocity()
elif nav_selection == "🌡 Calendar Heatmap":
    calendar_heatmap()
elif nav_selection == "🌳 Treemap":
    treemap_resource_distribution()
elif nav_selection == "🤖 AI PM Buddy":
    ai_pm_buddy_assistant()
