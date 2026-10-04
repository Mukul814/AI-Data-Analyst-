import { useEffect, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BarChart3, CircleHelp, Database, FileSpreadsheet, FolderOpen, LayoutDashboard, LoaderCircle, Plus, Send, Sparkles, Upload, X, Trash2 } from 'lucide-react';
import { api } from './api';
import { runAnalysisRequest } from './analysisFlow';
import type { Analysis, Dataset, Project } from './types';
import { AnalysisChart } from './components/AnalysisChart';
import './analysis.css';

type Page = 'overview' | 'projects' | 'datasets' | 'project' | 'help';
function storedId(key: string) { try { return localStorage.getItem(key) || undefined; } catch { return undefined; } }

export default function App() {
  const qc = useQueryClient();
  const { data: projects = [], isLoading, error } = useQuery({ queryKey: ['projects'], queryFn: api.projects });
  const [selectedProjectId, setSelectedProjectId] = useState<string | undefined>(() => storedId('datawise.projectId'));
  const projectQuery = useQuery({ queryKey: ['project', selectedProjectId], queryFn: () => api.project(selectedProjectId!), enabled: !!selectedProjectId });
  const selectedProject = projectQuery.data || projects.find(project => project.id === selectedProjectId);
  const [page, setPage] = useState<Page>('overview');
  const [active, setActive] = useState<Dataset | null>(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | undefined>(() => storedId('datawise.datasetId'));
  const [question, setQuestion] = useState('');
  const [conversation, setConversation] = useState<string>();
  const [answer, setAnswer] = useState<Analysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [projectName, setProjectName] = useState('');
  const [nameError, setNameError] = useState('');

  useEffect(() => {
    if (error) return;
    try {
      if (selectedProjectId) localStorage.setItem('datawise.projectId', selectedProjectId);
      else localStorage.removeItem('datawise.projectId');
      if (selectedDatasetId) localStorage.setItem('datawise.datasetId', selectedDatasetId);
      else localStorage.removeItem('datawise.datasetId');
    } catch { /* Storage can be unavailable in private browsing. */ }
  }, [selectedProjectId, selectedDatasetId]);

  useEffect(() => {
    if (error) return;
    if (isLoading) return;
    if (!selectedProjectId) { setActive(null); setSelectedDatasetId(undefined); return; }
    const project = projects.find(item => item.id === selectedProjectId)
      || (projectQuery.data?.id === selectedProjectId ? projectQuery.data : undefined);
    if (!project && projectQuery.isLoading) return;
    if (!project) {
      setSelectedProjectId(undefined); setSelectedDatasetId(undefined); setActive(null);
      return;
    }
    setPage('project');
    const dataset = selectedDatasetId && project.datasets.find(item => item.id === selectedDatasetId);
    if (dataset) setActive(dataset);
    else { setActive(null); if (selectedDatasetId) setSelectedDatasetId(undefined); }
  }, [projects, isLoading, error, selectedProjectId, selectedDatasetId, projectQuery.data, projectQuery.isLoading]);

  const create = useMutation({
    mutationFn: (name: string) => api.createProject(name),
    onSuccess: async project => {
      qc.setQueryData(['project', project.id], project);
      setSelectedProjectId(project.id);
      setActive(null);
      setSelectedDatasetId(undefined);
      setAnswer(null);
      setConversation(undefined);
      setPage('project');
      await qc.invalidateQueries({ queryKey: ['projects'] });
    },
    onError: e => setNotice(e.message),
  });
  const removeProject = useMutation({
    mutationFn: (id: string) => api.deleteProject(id),
    onSuccess: async (_, id) => {
      const wasSelected = selectedProjectId === id;
      await qc.invalidateQueries({ queryKey: ['projects'] });
      qc.removeQueries({ queryKey: ['project', id] });
      if (wasSelected) {
        setSelectedProjectId(undefined); setSelectedDatasetId(undefined); setActive(null);
        setAnswer(null); setConversation(undefined); setPage('projects');
      }
      setNotice('Project deleted.');
    },
    onError: e => setNotice(e.message),
  });
  const upload = useMutation({
    mutationFn: ({ projectId, file }: { projectId: string; file: File }) => api.upload(projectId, file),
    onSuccess: async dataset => {
      setSelectedProjectId(dataset.project_id);
      setActive(dataset);
      setSelectedDatasetId(dataset.id);
      setAnswer(null);
      setConversation(undefined);
      setNotice('Dataset profiled and ready to explore.');
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['projects'] }),
        qc.invalidateQueries({ queryKey: ['project', dataset.project_id] }),
      ]);
    },
    onError: e => setNotice(e.message),
  });

  function openProject(project: Project) {
    setSelectedProjectId(project.id);
    setActive(null);
    setSelectedDatasetId(undefined);
    setAnswer(null);
    setConversation(undefined);
    setPage('project');
  }

  function beginCreateProject() {
    setProjectName(''); setNameError(''); setCreateOpen(true);
  }

  function submitCreateProject(event: FormEvent) {
    event.preventDefault();
    const name = projectName.trim();
    if (!name) { setNameError('Enter a project name before continuing.'); return; }
    create.mutate(name, { onSuccess: () => { setCreateOpen(false); setProjectName(''); } });
  }

  function confirmDelete(project: Project) {
    if (window.confirm(`Delete “${project.name}” and its datasets? This cannot be undone.`)) {
      removeProject.mutate(project.id);
    }
  }

  async function submit(q = question) {
    if (!active || !q.trim()) return;
    setQuestion(q);
    setNotice('');
    try {
      const result = await runAnalysisRequest(
        () => api.ask(active.id, q, conversation),
        setBusy,
        () => setAnswer(null),
        setAnswer,
      );
      setConversation(result.conversation_id);
      setQuestion('');
    } catch (e) {
      setNotice(e instanceof Error ? e.message : 'Analysis failed');
    }
  }

  const fileInput = <input type="file" accept=".csv,.xlsx" className="hidden" onChange={e => {
    const file = e.target.files?.[0];
    if (file) {
      const uploadTo = (projectId: string) => upload.mutate({ projectId, file });
      if (selectedProjectId) uploadTo(selectedProjectId);
      else create.mutate('Untitled project', { onSuccess: project => uploadTo(project.id) });
    }
    e.currentTarget.value = '';
  }}/>;

  function selectDataset(dataset: Dataset) {
    setSelectedProjectId(dataset.project_id);
    setActive(dataset);
    setSelectedDatasetId(dataset.id);
    setAnswer(null);
    setConversation(undefined);
    setPage('project');
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><BarChart3 size={18}/></span><span>datawise<span className="brand-dot">.</span></span></div>
      <div className="workspace-switch" aria-label="Current workspace"><span className="workspace-avatar">M</span><span className="workspace-name">My workspace<small>Free plan</small></span></div>
      <div className="nav-label">WORKSPACE</div>
      <nav>
        <button className={`nav-item ${page === 'overview' ? 'active' : ''}`} onClick={() => { setPage('overview'); setActive(null); setSelectedDatasetId(undefined); }}><LayoutDashboard size={17}/>Overview</button>
        <button className={`nav-item ${page === 'projects' ? 'active' : ''}`} onClick={() => { setPage('projects'); setActive(null); setSelectedDatasetId(undefined); }}><FolderOpen size={17}/>Projects</button>
        <button className={`nav-item ${page === 'datasets' ? 'active' : ''}`} onClick={() => { setPage('datasets'); setActive(null); setSelectedDatasetId(undefined); }}><Database size={17}/>Datasets</button>
      </nav>
      <div className="nav-label recent-label">RECENT PROJECTS</div>
      <div className="project-nav">{projects.map(project => <button key={project.id} className={`nav-item ${selectedProjectId === project.id ? 'active' : ''}`} onClick={() => openProject(project)}><span className="project-dot"/>{project.name}</button>)}</div>
      <button className="new-project" onClick={beginCreateProject}><Plus size={16}/>New project</button>
      <div className="sidebar-bottom"><button className="nav-item" onClick={() => setPage('help')}><CircleHelp size={17}/>Help center</button><div className="profile" aria-label="Signed-in profile"><span className="avatar">MC</span><span>Mukul Chauhan<small>Personal workspace</small></span></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="breadcrumbs"><span>Workspace</span><span className="crumb-sep">/</span><b>{page === 'project' ? selectedProject?.name || 'Project' : page[0].toUpperCase() + page.slice(1)}</b></div><div className="top-right"><span className="connection"><i style={{ background: error ? '#c87861' : '#5aa378' }}/>{error ? 'API unavailable' : 'API connected'}</span><button className="help-button" onClick={() => setPage('help')}><CircleHelp size={16}/><span>Help</span></button></div></header>
      <div className="content">
        <div className="welcome-row"><div><div className="eyebrow"><Sparkles size={14}/>YOUR ANALYTICS WORKSPACE</div><h1>{page === 'project' ? selectedProject?.name || 'Project' : page === 'help' ? 'A little help' : 'Good morning, Mukul'} <span>✳</span></h1><p>{page === 'project' ? 'Your project, datasets, and analysis in one place.' : 'Turn your data into decisions. What would you like to explore today?'}</p></div><button className="button-primary" onClick={beginCreateProject}><Plus size={17}/>New project</button></div>
        {page === 'help' ? <section className="panel recent-panel"><div className="panel-head"><div><b>Getting started</b><small>Upload a dataset, then ask a question in plain language.</small></div></div><p className="answer-text">Supported uploads are CSV and XLSX. Analysis runs against your selected dataset using the available deterministic operations. Try asking for grouped totals, trends, missing values, summary statistics, outliers, correlations, or a baseline forecast.</p><button className="text-button" onClick={() => setPage('overview')}>Back to overview →</button></section>
        : page === 'projects' || page === 'datasets' ? <section className="panel recent-panel"><div className="panel-head"><div><b>{page === 'projects' ? 'Projects' : 'Datasets'}</b><small>{page === 'projects' ? 'Open a project or create a new one.' : 'Datasets across your projects.'}</small></div><button className="button-primary" onClick={beginCreateProject}><Plus size={15}/>New project</button></div>{error ? <div className="empty-state">Could not reach the API. Start the backend and refresh.</div> : isLoading ? <div className="empty-state">Loading workspace…</div> : page === 'projects' ? projects.map(project => <div className="recent-item" key={project.id}><span className="folder-icon"><FolderOpen size={17}/></span><span><b>{project.name}</b><small>{project.datasets.length} datasets</small></span><button onClick={() => openProject(project)}>Open project →</button><button className="delete-project" onClick={() => confirmDelete(project)} aria-label={`Delete ${project.name}`}><Trash2 size={14}/></button></div>) : projects.flatMap(project => project.datasets.map(dataset => <div className="recent-item" key={dataset.id}><span className="folder-icon"><FileSpreadsheet size={17}/></span><span><b>{dataset.filename}</b><small>{project.name} · {dataset.profile.row_count.toLocaleString()} rows</small></span><button onClick={() => selectDataset(dataset)}>Open dataset →</button></div>))}{!projects.length && <div className="empty-state"><b>No {page} yet</b><button onClick={beginCreateProject}>Create a project</button></div>}{page === 'datasets' && projects.length > 0 && !projects.some(project => project.datasets.length > 0) && <div className="empty-state"><b>No datasets yet</b><span>Open a project and upload your first dataset.</span></div>}</section>
        : page === 'project' ? <>
          {projectQuery.isLoading && !selectedProject ? <section className="panel empty-state">Loading project…</section> : !selectedProject ? <section className="panel empty-state"><b>Project not found</b><button onClick={() => setPage('projects')}>View projects</button></section> : <>
            <div className="section-heading"><div><h3>{active ? 'Dataset overview' : selectedProject.name}</h3><p>{active ? 'A quick look at your data, before the questions begin.' : `${selectedProject.datasets.length} dataset${selectedProject.datasets.length === 1 ? '' : 's'} in this project.`}</p></div>{active && <button className="text-button" onClick={() => { setActive(null); setSelectedDatasetId(undefined); setAnswer(null); }}>Back to project <X size={14}/></button>}</div>
            {notice && <div className="notice" role="alert">{notice}<button onClick={() => setNotice('')} aria-label="Dismiss"><X size={15}/></button></div>}
            {!active ? <section className="panel recent-panel"><div className="panel-head"><div><b>Project datasets</b><small>Upload a dataset or choose one to explore.</small></div><label className="button-primary"><Upload size={15}/>{upload.isPending ? 'Uploading…' : 'Upload dataset'}{fileInput}</label></div>{selectedProject.datasets.length ? selectedProject.datasets.map(dataset => <div className="recent-item" key={dataset.id}><span className="folder-icon"><FileSpreadsheet size={17}/></span><span><b>{dataset.filename}</b><small>{dataset.profile.row_count.toLocaleString()} rows · {dataset.profile.column_count} columns</small></span><button onClick={() => selectDataset(dataset)}>Open dataset →</button></div>) : <div className="empty-state"><span className="empty-icon"><Database size={20}/></span><b>This project is ready for its first dataset</b><span>Upload a CSV or XLSX file to start exploring.</span><label className="button-primary"><Upload size={15}/>Upload dataset{fileInput}</label></div>}</section> : <>
              <section className="stats-grid"><Stat label="Total rows" value={active.profile.row_count.toLocaleString()} icon="↕"/><Stat label="Columns" value={active.profile.column_count} icon="▤"/><Stat label="Missing values" value={active.profile.missing_cells} icon="◌"/><Stat label="Duplicate rows" value={active.profile.duplicate_rows} icon="⧉"/></section>
              <div className="workspace-grid"><section className="panel dataset-panel"><div className="panel-head"><div><span className="file-badge"><FileSpreadsheet size={17}/></span><span className="panel-title">{active.filename}<small>Uploaded dataset</small></span></div><span className="status-pill"><i/>Ready</span></div><div className="column-list"><div className="column-head"><span>Column</span><span>Type</span><span>Missing</span></div>{active.profile.columns.map(column => <div className="column-row" key={column.name}><b>{column.name}</b><span className="type-pill">{column.semantic_type}</span><span>{column.null_percentage}%</span></div>)}</div></section>
                <section className="panel ask-panel"><div className="ask-head"><span className="ai-badge"><Sparkles size={16}/></span><div><b>Ask your data</b><small>Questions are calculated against this dataset</small></div></div><div className="suggestions"><span>Try a suggestion or ask your own question</span>{['What are the top 5 categories by revenue?','Which columns have missing values?','How many rows are in the dataset?'].map(suggestion => <button key={suggestion} onClick={() => submit(suggestion)}>{suggestion}<span>↗</span></button>)}</div><form className="question-box" onSubmit={e => { e.preventDefault(); void submit(); }}><textarea value={question} onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void submit(); } }} placeholder="Ask any analytical question about this dataset…"/><div className="question-actions"><small>↵ Enter to send</small><button disabled={busy || !question.trim()} aria-label="Send question">{busy ? <LoaderCircle size={17} className="spin"/> : <Send size={16}/>}</button></div></form></section></div>
              {busy && <section className="panel result-panel analysis-loading" role="status"><LoaderCircle className="spin" size={17}/> Calculating this analysis…</section>}
              {answer && <section className="panel result-panel"><div className="result-head"><span className="ai-badge"><Sparkles size={16}/></span><div><b>Analysis</b><small>{answer.analysis_type.replace('_', ' ')} · Calculated from the selected dataset</small></div></div><p className="answer-text">{answer.answer}</p>{answer.visualization && <AnalysisChart visualization={answer.visualization}/ >}{answer.insights?.length > 0 && <div className="analysis-details"><b>Insights</b><ul>{answer.insights.map((insight, index) => <li key={index}>{insight}</li>)}</ul></div>}{answer.warnings?.length > 0 && <div className="analysis-warning">{answer.warnings.map((warning, index) => <p key={index}>{warning}</p>)}</div>}{answer.result !== undefined && <details className="data-details"><summary>View computed details</summary><pre>{JSON.stringify(answer.result, null, 2)}</pre></details>}{answer.code && <details className="code-details"><summary>View analysis method</summary><pre>{answer.code}</pre></details>}</section>}
              <section className="panel preview-panel"><div className="preview-head"><div><b>Data preview</b><small>First {active.profile.preview.length} rows</small></div><span>{active.profile.memory_bytes.toLocaleString()} bytes in memory</span></div><div className="table-scroll"><table><thead><tr>{active.profile.columns.map(column => <th key={column.name}>{column.name}</th>)}</tr></thead><tbody>{active.profile.preview.map((row, index) => <tr key={index}>{active.profile.columns.map(column => <td key={column.name}>{String(row[column.name] ?? '—')}</td>)}</tr>)}</tbody></table></div></section>
            </>}
          </>}
        </> : <>
          <section className="hero-card"><div className="hero-copy"><div className="hero-kicker">A LITTLE CLARITY GOES A LONG WAY</div><h2>Your data has a story.<br/><em>Let’s find it.</em></h2><p>Upload a dataset and ask questions in plain English.<br/>Your analyst is ready when you are.</p><label className="button-light"><Upload size={16}/>{upload.isPending ? 'Uploading…' : 'Upload a dataset'}{fileInput}</label><div className="file-note"><span>CSV</span><span>XLSX</span><b>Up to 25 MB</b></div></div><div className="hero-art"><div className="art-glow"/><div className="floating-tag tag-one"><span className="tag-icon mint">↗</span><span>Revenue trend<small>Analysis preview</small></span></div><div className="chart-card"><div className="chart-card-top"><span>Monthly revenue</span><b>Trend</b></div><div className="mini-bars">{[35,49,43,64,55,79,67,92,72,84,65,100].map((value, index) => <i key={index} style={{ height: `${value}%`, opacity: .38 + index * .047 }}/>)}</div><div className="chart-labels"><span>JAN</span><span>MAR</span><span>MAY</span><span>JUL</span></div></div><div className="floating-tag tag-two"><span className="tag-icon purple">✦</span><span>Explore your data<small>Ask an analytical question</small></span></div><div className="art-star">✳</div></div></section>
          <div className="section-heading"><div><h3>Your workspace</h3><p>Everything you need to start exploring your data.</p></div><button className="text-button" onClick={() => setPage('projects')}>View all projects →</button></div>
          {notice && <div className="notice" role="alert">{notice}<button onClick={() => setNotice('')} aria-label="Dismiss"><X size={15}/></button></div>}
          <section className="stats-grid"><Stat label="Active projects" value={projects.length} icon="▦"/><Stat label="Datasets" value={projects.reduce((total, project) => total + project.datasets.length, 0)} icon="▤"/><Stat label="Analysis sessions" value="—" icon="✳"/><Stat label="Analysis mode" value="Deterministic" icon="⌘"/></section>
          <div className="workspace-grid"><section className="panel recent-panel"><div className="panel-head"><div><b>Recent projects</b><small>Your latest workspaces</small></div><button className="text-button" onClick={() => setPage('projects')}>View all →</button></div>{isLoading ? <div className="empty-state">Loading workspace…</div> : error ? <div className="empty-state">Could not reach the API. Start the backend and refresh.</div> : projects.length ? projects.map(project => <div className="recent-item" key={project.id}><span className="folder-icon"><FolderOpen size={17}/></span><span><b>{project.name}</b><small>{project.datasets.length} datasets</small></span><button onClick={() => openProject(project)}>Open project →</button><button className="delete-project" onClick={() => confirmDelete(project)} aria-label={`Delete ${project.name}`}><Trash2 size={14}/></button></div>) : <div className="empty-state"><span className="empty-icon"><Database size={20}/></span><b>A fresh start</b><span>Create a project, then upload your first dataset.</span><button onClick={beginCreateProject}>Create your first project</button></div>}</section><section className="panel quick-panel"><div className="quick-icon"><Sparkles size={17}/></div><h3>From raw data<br/>to real answers.</h3><p>Ask in plain English. Supported calculations run against your selected dataset.</p><div className="quick-example"><span>✦</span> “Which region had the most sales?”</div><div className="quick-example"><span>✦</span> “Plot monthly revenue”</div></section></div>
        </>}
        {createOpen && <div className="modal-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) setCreateOpen(false); }}><form className="project-modal" onSubmit={submitCreateProject} role="dialog" aria-modal="true" aria-labelledby="new-project-title"><button type="button" className="modal-close" aria-label="Close" onClick={() => setCreateOpen(false)}><X size={17}/></button><h2 id="new-project-title">Create a project</h2><p>Choose a name for this workspace.</p><label htmlFor="project-name">Project name</label><input id="project-name" autoFocus maxLength={160} value={projectName} onChange={event => { setProjectName(event.target.value); setNameError(''); }} placeholder="e.g. Q3 Sales Analysis"/>{nameError && <div className="field-error" role="alert">{nameError}</div>}{create.isError && <div className="field-error" role="alert">{create.error.message}</div>}<div className="modal-actions"><button type="button" className="modal-cancel" onClick={() => setCreateOpen(false)}>Cancel</button><button className="button-primary" disabled={create.isPending}>{create.isPending ? 'Creating…' : 'Create project'}</button></div></form></div>}
        <footer>Thoughtful analysis starts with good questions. <span>Built for curious minds <b>✳</b></span></footer>
      </div>
    </main>
  </div>;
}

function Stat({ label, value, icon }: { label: string; value: string | number; icon: string }) {
  return <div className="stat-card"><span className="stat-icon">{icon}</span><div><small>{label}</small><b>{value}</b></div><span className="stat-spark">↗</span></div>;
}
