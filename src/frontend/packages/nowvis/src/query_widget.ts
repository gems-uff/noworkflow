import { Widget } from '@lumino/widgets';
import { select as d3_select, Selection as d3_Selection, BaseType as d3_BaseType } from 'd3-selection';
import { NowVisPanel } from './nowpanel';
import { TableInfoWidget } from './database_widget';
import 'ace-builds/src-noconflict/ace';
import 'ace-builds/src-noconflict/theme-textmate';
import 'ace-builds/src-noconflict/mode-sql';
import 'ace-builds/src-noconflict/ext-language_tools';

declare global { interface Window { ace: any; } }

export class DatabaseTabWidget extends Widget {}

export class QueryResultWidget extends DatabaseTabWidget {
  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  private columns: string[];
  private rows: any[];
  private query: string;
  private currentPage: number = 1;
  
  constructor(query: string, columns: string[], rows: any[], count: number) {
    super({ node: QueryResultWidget.createNode() });
    this.title.label = `Query Result (${count})`;
    this.title.caption = `Query Result (${count})`;
    this.title.closable = true;
    this.d3node = d3_select(this.node);
    this.query = query;
    this.columns = columns;
    this.rows = rows;
    this.renderTable();
  }
  
  static createNode(): HTMLElement {
    const node = document.createElement('div');
    node.style.padding = '1rem';
    node.style.height = '100%';
    node.style.overflowY = 'auto';
    return node;
  }
  
  private renderTable(): void {
    this.d3node.selectAll('*').remove();
    
    this.d3node.append('a')
      .classed("toollink", true)
      .attr('class', 'btn btn-secondary-outline')
      .attr('title', 'Download CSV')
      .style('margin-bottom', '1em')
      .on('click', () => {
        let csv = '';
        csv += this.columns.map(col => `"${col.replace(/"/g, '""')}"`).join(',') + '\n';
        for (const row of this.rows) {
          csv += this.columns.map(col => `"${String(row[col] !== undefined ? row[col] : '').replace(/"/g, '""')}"`).join(',') + '\n';
        }
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'query_result.csv';
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        }, 100);
      })
      .append("i")
      .classed("fa fa-download", true);

    if (!this.columns.length || !this.rows.length) {
      this.d3node.append('div').text('No results.');
      return;
    }

    const paginationContainer = this.d3node.append('div')
      .style('display', 'flex')
      .style('justify-content', 'space-between')
      .style('align-items', 'center')
      .style('margin-bottom', '1rem')
      .style('padding', '0.5rem')
      .style('background-color', '#f8f9fa')
      .style('border-radius', '4px');

    const startIndex = (this.currentPage - 1) * 50 + 1;
    const endIndex = Math.min(this.currentPage * 50, this.rows.length);
    paginationContainer.append('div')
      .style('font-size', '0.9em')
      .style('color', '#666')
      .text(`Showing ${startIndex}-${endIndex} of ${this.rows.length} rows`);

    const paginationButtons = paginationContainer.append('div')
      .style('display', 'flex')
      .style('gap', '0.25rem');

    const totalPages = Math.ceil(this.rows.length / 50);

    if (totalPages > 1) {
      paginationButtons.append('button')
        .attr('class', 'btn btn-sm btn-outline-secondary')
        .on('click', () => {
          this.currentPage = 1;
          this.renderTable();
        })
        .text('<<');
      
      paginationButtons.append('button')
        .attr('class', 'btn btn-sm btn-outline-secondary')
        .on('click', () => {
          this.currentPage--;
          this.renderTable();
        })
        .text('<');
      
      paginationButtons.append('button')
        .attr('class', 'btn btn-sm btn-primary')
        .text(this.currentPage.toString());
      
      paginationButtons.append('button')
        .attr('class', 'btn btn-sm btn-outline-secondary')
        .on('click', () => {
          this.currentPage++;
          this.renderTable();
        })
        .text('>');
      
      paginationButtons.append('button')
        .attr('class', 'btn btn-sm btn-outline-secondary')
        .on('click', () => {
          this.currentPage = totalPages;
          this.renderTable();
        })
        .text('>>');
    }

    const tableContainer = this.d3node.append('div')
      .style('max-height', '400px')
      .style('overflow-y', 'auto')
      .style('border', '1px solid #dee2e6')
      .style('border-radius', '4px');
    
    const table = tableContainer.append('table').attr('class', 'table table-bordered table-sm');
    table.style('border-collapse', 'separate')
      .style('border-spacing', '0');

    const thead = table.append('thead').append('tr');
    thead.style('position', 'sticky')
      .style('top', '0')
      .style('background-color', 'white')
      .style('z-index', '1');

    this.columns.forEach(col => thead.append('th').text(col));
    
    const tbody = table.append('tbody');
    
    const startRow = (this.currentPage - 1) * 50;
    const endRow = Math.min(startRow + 50, this.rows.length);
    const currentPageRows = this.rows.slice(startRow, endRow);
    
    currentPageRows.forEach(row => {
      const tr = tbody.append('tr');
      this.columns.forEach(col => tr.append('td').text(row[col] !== undefined ? row[col] : ''));
    });

    this.d3node.append('div')
      .attr('class', 'text-muted')
      .style('margin-top', '1rem')
      .style('margin-bottom', '0.5em')
      .html(`<b>Query:</b> <code>${this.query}</code>`);
  }
}

export class QueryWidget extends Widget {
  private panel: NowVisPanel;
  private static count: number = 0;
  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  private aceEditor: any; // Ace editor instance
  private tableNames: string[] = [];
  private editorId: string;
  private initialQuery: string;
  
  constructor(panel: NowVisPanel, tableNames?: string[], initialQuery?: string) {
    super();
    this.panel = panel;
    this.title.label = 'SQL Query';
    this.title.caption = 'SQL Query Interface';
    this.title.closable = true;
    this.d3node = d3_select(this.node);
    this.tableNames = tableNames || [];
    this.editorId = `query-input-${++QueryWidget.count}`;
    this.initialQuery = initialQuery || '';

    this.createQueryInterface();
  }

  private async createQueryInterface(): Promise<void> {
    const container = this.d3node.append('div')
      .style('display', 'flex')
      .style('flex-direction', 'column')
      .style('height', '100%')
      .style('padding', '1rem')
      .style('gap', '1rem')
      .style('overflow-y', 'auto')
      .style('overflow-x', 'hidden');

    const headerRow = container.append('div')
      .style('display', 'flex')
      .style('justify-content', 'space-between')
      .style('align-items', 'center')
      .style('margin-bottom', '1rem')
      .style('flex-shrink', '0');

    headerRow.append('h4')
      .text('SQL Query Interface')
      .style('margin', '0')
      .style('color', '#333');

    headerRow.append('button')
      .attr('id', 'execute-query-btn')
      .attr("title", "Execute query. Use Ctrl+Enter for quick execution.")
      .classed('btn btn-primary', true)
      .on('click', () => this.executeQuery())
      .html('<i class="fa fa-play" style="margin-left:4px;"></i> Execute Query');

    const queryContainer = container.append('div')
      .style('display', 'flex')
      .style('flex-direction', 'column')
      .style('min-height', '50%')
      .style('flex', '1 1 0');
    
    queryContainer.append('label')
      .attr('for', this.editorId)
      .text('Enter your SQL query:')
      .style('font-weight', 'bold')
      .style('margin-bottom', '0.5rem');
    
    queryContainer.append('div')
      .attr('id', this.editorId)
      .style('width', '100%')
      .style('min-height', '140px')
      .style('max-height', '30vh')
      .style('border', '1px solid #ccc')
      .style('border-radius', '4px')
      .style('font-size', '1em')
      .style('flex', '1');

    setTimeout(() => {
      // @ts-ignore
      this.aceEditor = window.ace.edit(this.editorId);
      this.aceEditor.setTheme('ace/theme/textmate');
      this.aceEditor.session.setMode('ace/mode/sql');
      this.aceEditor.setOptions({
        fontSize: '1em',
        minLines: 6,
        showPrintMargin: false,
        enableBasicAutocompletion: true,
        enableLiveAutocompletion: true,
      });
      this.aceEditor.commands.addCommand({
        name: 'executeQuery',
        bindKey: { win: 'Ctrl-Enter', mac: 'Command-Enter' },
        exec: () => this.executeQuery()
      });

      if (window.ace && window.ace.require) {
        const langTools = window.ace.require('ace/ext/language_tools');
        const tableCompleter = {
          getCompletions: (editor: any, session: any, pos: any, prefix: string, callback: any) => {
            if (!prefix) { callback(null, []); return; }
            const completions = (this.tableNames || []).map((name: string) => ({
              caption: name,
              value: name,
              meta: 'table'
            }));
            callback(null, completions);
          }
        };
        langTools.addCompleter(tableCompleter);
      }

      if (this.initialQuery) {
        this.aceEditor.setValue(this.initialQuery);
        this.aceEditor.clearSelection();
        this.aceEditor.focus();
      }
    }, 0);
    
    queryContainer.append('div')
      .attr('id', `query-status-${this.editorId}`)
      .style('min-height', '60px')
      .style('padding', '0.5rem')
      .style('border', '1px solid #e0e0e0')
      .style('border-radius', '4px')
      .style('background-color', '#f9f9f9')
      .style('font-family', 'monospace')
      .style('font-size', '0.9em')
      .style('overflow-y', 'auto')
      .style('flex-shrink', '0')
      .style('margin-top', '1rem')
      .text('Ready to execute queries. Use Ctrl+Enter for quick execution.');
  }

  private async executeQuery(): Promise<void> {
    // const queryInput = this.node.querySelector('#query-input') as HTMLTextAreaElement;
    const statusArea = this.node.querySelector(`#query-status-${this.editorId}`) as HTMLDivElement;
    
    const sql = this.aceEditor ? this.aceEditor.getValue().trim() : '';
    
    if (!statusArea) return;
    
    statusArea.innerHTML = '';
    statusArea.style.color = '#333';
    
    if (!sql) {
      statusArea.textContent = 'Please enter a SQL query.';
      statusArea.style.color = '#d32f2f';
      return;
    }

    statusArea.textContent = 'Executing query...';
    statusArea.style.color = '#1976d2';
    
    try {
      const response = await fetch('/db/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: sql })
      });
      
      const data = await response.json();
      
      if (data.error) {
        statusArea.textContent = `Error: ${data.error}`;
        statusArea.style.color = '#d32f2f';
      } else if (data.rows && data.columns) {
        statusArea.textContent = `Query executed successfully! Found ${data.rows.length} rows with ${data.columns.length} columns.`;
        statusArea.style.color = '#388e3c';
        
        await this.displayQueryResults(sql, data.columns, data.rows);
      } else {
        statusArea.textContent = 'Query executed successfully. No results returned.';
        statusArea.style.color = '#388e3c';
      }
    } catch (e) {
      statusArea.textContent = `Error executing query: ${e.message}`;
      statusArea.style.color = '#d32f2f';
    }
  }

  private async displayQueryResults(sql: string, columns: string[], rows: any[]): Promise<void> {
    const resultWidget = new QueryResultWidget(sql, columns, rows, ++QueryWidget.count);
    
    let refWidget: Widget | null = null;
    if (this.panel.widgets) {
      for (let w of this.panel.widgets()) {
        if (w instanceof TableInfoWidget || w instanceof QueryResultWidget) {
          refWidget = w;
        }
      }
    }
    
    if (refWidget) {
      this.panel.addInfoWidget(resultWidget, { ref: refWidget, mode: 'tab-after' });
    } else {
      this.panel.addInfoWidget(resultWidget, { ref: this, mode: 'split-bottom' });
    }
    
    this.panel.activateWidget(resultWidget);
  }

  protected onResize(msg: Widget.ResizeMessage): void {
    const editorElement = this.node.querySelector(`#${this.editorId}`) as HTMLElement;
    if (!editorElement) 
      return;

    const rect = this.node.getBoundingClientRect();
    const availableHeight = rect.height - 200;
    const minHeight = 250;
    const maxHeight = Math.max(minHeight, availableHeight * 0.6);
    editorElement.style.height = `${maxHeight}px`;
    
    if (this.aceEditor) {
      this.aceEditor.resize();
    }
  }
} 
