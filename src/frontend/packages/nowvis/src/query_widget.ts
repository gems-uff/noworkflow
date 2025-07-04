import { Widget } from '@lumino/widgets';
import { select as d3_select, Selection as d3_Selection, BaseType as d3_BaseType } from 'd3-selection';
import { NowVisPanel } from './nowpanel';
import { TableInfoWidget } from './database_widget';

export class DatabaseTabWidget extends Widget {}

export class QueryResultWidget extends DatabaseTabWidget {
  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  constructor(query: string, columns: string[], rows: any[], count: number) {
    super({ node: QueryResultWidget.createNode(query, columns, rows) });
    this.title.label = `Query Result (${count})`;
    this.title.caption = `Query Result (${count})`;
    this.title.closable = true;
    this.d3node = d3_select(this.node);
  }
  static createNode(query: string, columns: string[], rows: any[]): HTMLElement {
    const node = document.createElement('div');
    node.style.padding = '1rem';
    const d3node = d3_select(node);

    // Download CSV 
    d3node.append('a')
      .classed("toollink", true)
      .attr('class', 'btn btn-secondary-outline')
      .attr('title', 'Download CSV')
      .style('margin-bottom', '1em')
      .on('click', () => {
        let csv = '';
        csv += columns.map(col => `"${col.replace(/"/g, '""')}"`).join(',') + '\n';
        for (const row of rows) {
          csv += columns.map(col => `"${String(row[col] !== undefined ? row[col] : '').replace(/"/g, '""')}"`).join(',') + '\n';
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

    if (!columns.length) {
      d3node.append('div').text('No results.');
    } else {
      const table = d3node.append('table').attr('class', 'table table-bordered table-sm');
      const thead = table.append('thead').append('tr');
      columns.forEach(col => thead.append('th').text(col));
      const tbody = table.append('tbody');
      rows.forEach(row => {
        const tr = tbody.append('tr');
        columns.forEach(col => tr.append('td').text(row[col] !== undefined ? row[col] : ''));
      });
    }
    d3node.append('div')
      .attr('class', 'text-muted')
      .style('margin-bottom', '0.5em')
      .html(`<b>Query:</b> <code>${query}</code>`);
    return node;
  }
}

export class QueryWidget extends Widget {
  private panel: NowVisPanel;
  private static count: number = 0;
  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  
  constructor(panel: NowVisPanel) {
    super();
    this.panel = panel;
    this.title.label = 'SQL Query';
    this.title.caption = 'SQL Query Interface';
    this.title.closable = true;
    
    // Criar estrutura com D3
    this.d3node = d3_select(this.node);
    
    this.createQueryInterface();
  }

  private createQueryInterface(): void {
    // Main container
    const container = this.d3node.append('div')
      .style('display', 'flex')
      .style('flex-direction', 'column')
      .style('height', '100%')
      .style('padding', '1rem')
      .style('gap', '1rem');

    // Title
    container.append('h4')
      .text('SQL Query Interface')
      .style('margin', '0 0 1rem 0')
      .style('color', '#333');

    // Query container (textarea + button)
    const queryContainer = container.append('div')
      .style('display', 'flex')
      .style('flex-direction', 'column')
      .style('min-height', '50%')
      .style('flex', '1 1 0');
    
    // Label for textarea
    queryContainer.append('label')
      .attr('for', 'query-input')
      .text('Enter your SQL query:')
      .style('font-weight', 'bold')
      .style('margin-bottom', '0.5rem');
    
    // Textarea for query
    queryContainer.append('textarea')
      .attr('id', 'query-input')
      .style('width', '100%')
      .style('font-family', 'monospace')
      .style('font-size', '1em')
      .style('padding', '0.75rem')
      .style('border', '1px solid #ccc')
      .style('border-radius', '4px')
      .style('resize', 'vertical')
      .style('min-height', '140px')
      .style('max-height', '30vh')
      .style('flex', '1')
      .style('margin-bottom', '1rem')
      .attr('placeholder', 'SELECT * FROM table_name;')
      .on('keydown', (event: KeyboardEvent) => {
        if (event.ctrlKey && event.key === 'Enter') {
          event.preventDefault();
          this.executeQuery();
        }
      });
    
    const buttonContainer = queryContainer.append('div')
      .style('display', 'flex')
      .style('gap', '0.5rem')
      .style('justify-content', 'flex-end')
      .style('flex-shrink', '0');
    
    // Execute query 
    buttonContainer.append('button')
      .attr('id', 'execute-query-btn')
      .attr("title", "Execute query. Use Ctrl+Enter for quick execution.")
      .classed('btn btn-primary', true)
      .on('click', () => this.executeQuery())
      .html('<i class="fa fa-play" style="margin-left:4px;"></i> Execute Query');
    
    // Status/messages area
    container.append('div')
      .attr('id', 'query-status')
      .style('min-height', '60px')
      .style('padding', '0.5rem')
      .style('border', '1px solid #e0e0e0')
      .style('border-radius', '4px')
      .style('background-color', '#f9f9f9')
      .style('font-family', 'monospace')
      .style('font-size', '0.9em')
      .style('overflow-y', 'auto')
      .text('Ready to execute queries. Use Ctrl+Enter for quick execution.');
  }

  private async executeQuery(): Promise<void> {
    const queryInput = this.node.querySelector('#query-input') as HTMLTextAreaElement;
    const statusArea = this.node.querySelector('#query-status') as HTMLDivElement;
    
    if (!queryInput || !statusArea) return;
    
    // Clear status 
    statusArea.innerHTML = '';
    statusArea.style.color = '#333';
    
    const sql = queryInput.value.trim();
    
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
        
        // Display results in new tab
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
    const textarea = this.node.querySelector('#query-input') as HTMLTextAreaElement;
    if (!textarea) 
      return;

    const rect = this.node.getBoundingClientRect();
    const availableHeight = rect.height - 200;
    const minHeight = 250;
    const maxHeight = Math.max(minHeight, availableHeight * 0.6);
    textarea.style.height = `${maxHeight}px`;
  }
} 
