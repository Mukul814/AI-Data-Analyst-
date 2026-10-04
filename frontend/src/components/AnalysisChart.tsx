import { Component, type ErrorInfo, type ReactNode } from 'react';
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { Visualization } from '../types';

const colors = ['#28745a', '#94b876', '#d8ef83', '#7395c5', '#d39d63', '#9a83bf'];

export function AnalysisChart({ visualization }: { visualization: Visualization }) {
  try {
    const rows = visualization.data.filter(row => Object.values(row).some(value => value !== null && value !== undefined));
    const x = visualization.x || Object.keys(rows[0] || {})[0];
    const y = visualization.y || Object.keys(rows[0] || {}).find(key => key !== x);
    if (!rows.length || !x || !y) return <p className="chart-empty">No chartable values were returned for this analysis.</p>;
    if (visualization.type === 'box') return <p className="chart-empty">This analysis returned a box-plot specification, which is not currently supported by the chart renderer.</p>;
    return <ChartBoundary><div className="chart-wrap"><h4>{visualization.title}</h4><ResponsiveContainer width="100%" height={260}>
      {visualization.type === 'line' ? <LineChart data={rows}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey={x}/><YAxis/><Tooltip/><Line dataKey={y} stroke="#28745a" strokeWidth={3} dot={false}/></LineChart>
        : visualization.type === 'scatter' ? <ScatterChart><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey={x} name={x}/><YAxis dataKey={y} name={y}/><Tooltip cursor={{ strokeDasharray: '3 3' }}/><Scatter data={rows} fill="#28745a"/></ScatterChart>
          : visualization.type === 'pie' ? <PieChart><Tooltip/><Pie data={rows} dataKey={y} nameKey={x} outerRadius="78%" label>{rows.map((_, index) => <Cell key={index} fill={colors[index % colors.length]}/>)}</Pie></PieChart>
            : <BarChart data={rows}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey={x}/><YAxis/><Tooltip/><Bar dataKey={y} fill="#28745a" radius={[5,5,0,0]}>{rows.map((_, index) => <Cell key={index} fill={colors[index % colors.length]}/>)}</Bar></BarChart>}
    </ResponsiveContainer></div></ChartBoundary>;
  } catch {
    return <p className="chart-empty">The analysis completed, but its chart could not be displayed.</p>;
  }
}

class ChartBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(_error: Error, _info: ErrorInfo) { /* Keep chart rendering isolated from the analysis result. */ }
  render() { return this.state.failed ? <p className="chart-empty">The analysis completed, but its chart could not be displayed.</p> : this.props.children; }
}
