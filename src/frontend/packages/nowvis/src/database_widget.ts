import { Widget } from '@lumino/widgets';
import { Message } from '@lumino/messaging';
import { select as d3_select, Selection as d3_Selection, BaseType as d3_BaseType } from 'd3-selection';
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide, SimulationNodeDatum, SimulationLinkDatum } from 'd3-force';
import { scaleOrdinal } from 'd3-scale';
import { schemeTableau10 } from 'd3-scale-chromatic';
import { drag } from 'd3-drag';
import { NowVisPanel } from './nowpanel';
import { QueryWidget, QueryResultWidget } from './query_widget';

interface TableNode extends SimulationNodeDatum {
  id: string;
  name: string;
  selected?: boolean;
}

interface TableLink extends SimulationLinkDatum<TableNode> {
  source: string | TableNode;
  target: string | TableNode;
  sourceColumn: string;
  targetColumn: string;
}

interface DatabaseGraphData {
  nodes: TableNode[];
  links: TableLink[];
}

export class DatabaseTabWidget extends Widget {}

export class TableInfoWidget extends DatabaseTabWidget {
  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  constructor(tableName: string, details: any) {
    super({ node: TableInfoWidget.createNode(tableName, details) });
    this.title.label = tableName;
    this.title.caption = `Table: ${tableName}`;
    this.title.closable = true;
    this.d3node = d3_select(this.node);
  }
  static createNode(tableName: string, details: any): HTMLElement {
    const node = document.createElement('div');
    
    node.style.display = 'flex';
    node.style.flexDirection = 'column';
    node.style.height = '100%';
    node.style.overflow = 'hidden';
    
    const header = d3_select(node).append('div')
      .style('flex-shrink', '0')
      .style('padding', '1rem')
      .style('border-bottom', '1px solid #eee')
      .style('background', '#f8f9fa');
    
    header.append('h4')
      .text(tableName)
      .style('margin', '0')
      .style('color', '#333');
    
    const contentContainer = d3_select(node).append('div')
      .style('flex', '1')
      .style('overflow-y', 'auto')
      .style('overflow-x', 'hidden')
      .style('padding', '1rem');
    
    if (details.error) {
      contentContainer.append('div')
        .style('color', 'red')
        .text('Failed to load table details.');
    } else {
      contentContainer.append('h5')
        .text('Columns')
        .style('margin-top', '0')
        .style('margin-bottom', '1rem')
        .style('color', '#495057');
        
      const columnsTable = contentContainer.append('table')
        .attr('class', 'table table-sm table-bordered')
        .style('width', '100%')
        .style('margin-bottom', '2rem');
        
      const columnsThead = columnsTable.append('thead').append('tr');
      for( const h of ['Name', 'Type', 'NOT NULL', 'Default', 'PK']){
        columnsThead.append('th').text(h).style('font-size', '0.875rem')
      };
        
      const columnsTbody = columnsTable.append('tbody');
      details.columns.forEach((col: any) => {
        const row = columnsTbody.append('tr');
        row.append('td').text(col.name).style('font-size', '0.875rem');
        row.append('td').text(col.type).style('font-size', '0.875rem');
        row.append('td').text(col.notnull ? 'Yes' : '').style('font-size', '0.875rem');
        row.append('td').text(col.default === null ? '' : col.default).style('font-size', '0.875rem');
        row.append('td').text(col.pk ? 'Yes' : '').style('font-size', '0.875rem');
      });

      if (details.foreign_keys && details.foreign_keys.length > 0) {
        contentContainer.append('h5')
          .text('Foreign Keys')
          .style('margin-top', '0')
          .style('margin-bottom', '1rem')
          .style('color', '#495057');
            
        const fkTable = contentContainer.append('table')
          .attr('class', 'table table-sm table-bordered')
          .style('width', '100%')
          .style('margin-bottom', '2rem');
            
        const fkThead = fkTable.append('thead').append('tr');
        for( const h of ['Column', 'References Table', 'References Column']){
          fkThead.append('th').text(h).style('font-size', '0.875rem');
        };
            
        const fkTbody = fkTable.append('tbody');
        for( const fk of details.foreign_keys){
          const row = fkTbody.append('tr');
          row.append('td').text(fk.from).style('font-size', '0.875rem');
          row.append('td').text(fk.table).style('font-size', '0.875rem');
          row.append('td').text(fk.to).style('font-size', '0.875rem');
        };
      }

      if (details.referenced_by && details.referenced_by.length > 0) {
        contentContainer.append('h5')
          .text('Referenced By')
          .style('margin-top', '0')
          .style('margin-bottom', '1rem')
          .style('color', '#495057');
          
        const columnReferences: { [key: string]: any[] } = {};
        details.referenced_by.forEach((ref: any) => {
          if (!columnReferences[ref.referenced_column]) {
            columnReferences[ref.referenced_column] = [];
          }
          columnReferences[ref.referenced_column].push(ref);
        });

        const refTable = contentContainer.append('table')
          .attr('class', 'table table-sm table-bordered')
          .style('width', '100%')
          .style('margin-bottom', '2rem');
            
        const refThead = refTable.append('thead').append('tr');
        for( const h of ['Table', 'Column', 'References Column']){
          refThead.append('th').text(h).style('font-size', '0.875rem');
        };
            
        const refTbody = refTable.append('tbody');
        for( const ref of details.referenced_by){
          const row = refTbody.append('tr');
          row.append('td').text(ref.referencing_table).style('font-size', '0.875rem');
          row.append('td').text(ref.referencing_column).style('font-size', '0.875rem');
          row.append('td').text(ref.referenced_column).style('font-size', '0.875rem');
        };
      }
    }
    return node;
  }
}

export class DatabaseWidget extends Widget {
  panel: NowVisPanel;
  graphData: DatabaseGraphData = { nodes: [], links: [] };
  simulation: any;
  svg: d3_Selection<SVGSVGElement, {}, HTMLElement | null, any>;
  color: any;
  dataLoaded: boolean = false;
  selectedNodes: Set<string> = new Set();
  
  constructor(panel: NowVisPanel) {
    super();
    this.panel = panel;
    this.title.label = 'Database';
    this.title.caption = 'Database';
    
    const d3node = d3_select(this.node);
    
    const container = d3node.append('div')
      .style('display', 'flex')
      .style('flex-direction', 'column')
      .style('height', '100%')
      .style('padding', '1rem');

    const headerContainer = container.append('div')
      .style('display', 'flex')
      .style('justify-content', 'space-between')
      .style('align-items', 'center')
      .style('margin-bottom', '1rem');

    headerContainer.append('h4')
      .text('Database')
      .style('margin', '0')
      .style('color', '#333');

    const controlsContainer = headerContainer.append('div')
      .style('display', 'flex')
      .style('gap', '0.5rem')
      .style('align-items', 'center');

    const tablesDropdown = controlsContainer.append('div')
      .style('position', 'relative')
      .style('display', 'inline-block');

    const dropdownButton = tablesDropdown.append('button')
      .classed('btn btn-outline-primary dropdown-toggle', true)
      .attr('type', 'button')
      .attr('data-toggle', 'dropdown')
      .attr('aria-haspopup', 'true')
      .attr('aria-expanded', 'false')
      .html('<i class="fa fa-table" style="margin-right:4px;"></i>Tables <span class="caret"></span>')
      .style('min-width', '120px');

    tablesDropdown.append('div')
      .attr('id', 'tables-dropdown')
      .classed('dropdown-menu', true)
      .style('position', 'absolute')
      .style('top', '100%')
      .style('left', '0')
      .style('z-index', '1000')
      .style('display', 'none')
      .style('min-width', '250px')
      .style('max-height', '300px')
      .style('overflow-y', 'auto')
      .style('background', '#fff')
      .style('border', '1px solid #ccc')
      .style('border-radius', '4px')
      .style('box-shadow', '0 2px 10px rgba(0,0,0,0.1)')
      .style('padding', '0.5rem');

    controlsContainer.append('button')
      .attr('id', 'new-query-btn')
      .classed('btn btn-primary', true)
      .on('click', () => this.openNewQueryTab())
      .html('<i class="fa fa-plus" style="margin-right:4px;"></i> New Query');

    controlsContainer.append('button')
      .attr('id', 'clear-selection-btn')
      .classed('btn btn-outline-secondary', true)
      .style('display', 'none')
      .on('click', () => this.clearSelection())
      .html('<i class="fa fa-times" style="margin-right:2px;"></i> Clear Selection');

    container.append('div')
      .attr('id', 'graph-container')
      .style('flex', '1')
      .style('border', '1px solid #ddd')
      .style('border-radius', '4px')
      .style('background', '#f9f9f9')
      .style('position', 'relative');

    this.color = scaleOrdinal(schemeTableau10);

    dropdownButton.on('click', () => {
      const dropdown = document.getElementById('tables-dropdown');
      if (dropdown) {
        const isVisible = dropdown.style.display === 'block';
        dropdown.style.display = isVisible ? 'none' : 'block';
        dropdownButton.attr('aria-expanded', !isVisible);
      }
    });

    d3_select(document).on('click', (event) => {
      const dropdown = document.getElementById('tables-dropdown');
      const button = dropdownButton.node();
      if (dropdown && button && !button.contains(event.target) && !dropdown.contains(event.target)) {
        dropdown.style.display = 'none';
        dropdownButton.attr('aria-expanded', 'false');
      }
    });

    this.showLoadingMessage();
  }

  protected onAfterShow(msg: Message): void {
    this.fetchAndRenderTables();
  }

  private showLoadingMessage(): void {
    const container = this.node.querySelector('#graph-container') as HTMLElement;
    if (!container) return;

    d3_select(container).selectAll('*').remove();

    d3_select(container)
      .append('div')
      .style('display', 'flex')
      .style('justify-content', 'center')
      .style('align-items', 'center')
      .style('height', '100%')
      .style('flex-direction', 'column')
      .style('color', '#666')
      .style('font-size', '16px')
      .html(`
        <i class="fa fa-spinner fa-spin" style="font-size: 24px; margin-bottom: 10px;"></i>
        <div>Click on the Database tab to load database structure</div>
      `);
  }

  async fetchAndRenderTables() {
    const dropdownMenu = this.node.querySelector('#tables-dropdown');
    if (!dropdownMenu) {
      console.error('Tables dropdown element not found');
      return;
    }

    this.showLoadingState();
    this.clearSelection();

    try {
      const response = await fetch('/db/tables');
      if (!response.ok) throw new Error('Failed to fetch table list');
      const data = await response.json();
      this.renderTableList(data.tables);
      this.buildGraphDataFromTablesResponse(data);
      this.initializeGraph();
      this.renderGraph();
      this.dataLoaded = true;
    } catch (e) {
      console.error('Error fetching tables:', e);
      this.showErrorMessage('Failed to load database structure');
    }
  }

  private showLoadingState(): void {
    const container = this.node.querySelector('#graph-container') as HTMLElement;
    if (!container) return;

    d3_select(container).selectAll('*').remove();

    d3_select(container)
      .append('div')
      .style('display', 'flex')
      .style('justify-content', 'center')
      .style('align-items', 'center')
      .style('height', '100%')
      .style('flex-direction', 'column')
      .style('color', '#666')
      .style('font-size', '16px')
      .html(`
        <i class="fa fa-spinner fa-spin" style="font-size: 24px; margin-bottom: 10px;"></i>
        <div>Loading database structure...</div>
      `);
  }

  private showErrorMessage(message: string): void {
    const container = this.node.querySelector('#graph-container') as HTMLElement;
    if (!container) return;

    d3_select(container).selectAll('*').remove();

    d3_select(container)
      .append('div')
      .style('display', 'flex')
      .style('justify-content', 'center')
      .style('align-items', 'center')
      .style('height', '100%')
      .style('flex-direction', 'column')
      .style('color', '#dc3545')
      .style('font-size', '16px')
      .html(`
        <i class="fa fa-exclamation-triangle" style="font-size: 24px; margin-bottom: 10px;"></i>
        <div>${message}</div>
      `);
  }

  buildGraphDataFromTablesResponse(data: any) {
    const { tables, foreign_keys } = data;
    
    this.graphData.nodes = tables.map((tableName: string) => ({
      id: tableName,
      name: tableName
    }));

    this.graphData.links = [];

    if (foreign_keys) {
      Object.keys(foreign_keys).forEach(sourceTable => {
        const tableForeignKeys = foreign_keys[sourceTable];
        tableForeignKeys.forEach((fk: any) => {
          const existingLink = this.graphData.links.find(link => 
            link.source === sourceTable && link.target === fk.table
          );
          
          if (!existingLink) {
            this.graphData.links.push({
              source: sourceTable,
              target: fk.table,
              sourceColumn: fk.from,
              targetColumn: fk.to
            });
          }
        });
      });
    }
  }

  private createArrowMarker(): void {
    this.svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '-0 -3 6 6')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 5)
      .attr('markerHeight', 5)
      .attr('xoverflow', 'visible')
      .append('svg:path')
      .attr('d', 'M 0,-3 L 6 ,0 L 0,3')
      .attr('fill', '#999')
      .style('stroke', 'none');
  }

  private createSimulation(width: number, height: number, isInitial: boolean = false): void {
    if (this.simulation) {
      this.simulation.stop();
    }

    const linkDistance = isInitial ? 200 : 250;
    const chargeStrength = isInitial ? -200 : -400;
    const chargeDistanceMax = isInitial ? 800 : 400;
    const collisionRadius = isInitial ? 120 : 70;

    this.simulation = forceSimulation(this.graphData.nodes)
      .force('link', forceLink(this.graphData.links).id((d: any) => d.id).distance(linkDistance))
      .force('charge', forceManyBody().strength(chargeStrength).distanceMax(chargeDistanceMax))
      .force('center', forceCenter(width / 2, height / 2))
      .force('collision', forceCollide().radius(collisionRadius));

    if (!isInitial) {
      this.simulation.alphaDecay(0.1).velocityDecay(0.4);
    }
  }

  initializeGraph() {
    const container = this.node.querySelector('#graph-container') as HTMLElement;
    if (!container) return;

    d3_select(container).selectAll('*').remove();

    const rect = container.getBoundingClientRect();
    const width = Math.max(400, rect.width || 800);
    const height = Math.max(300, rect.height || 600);

    this.svg = d3_select(container)
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .style('background', '#f9f9f9') as d3_Selection<SVGSVGElement, {}, HTMLElement | null, any>;

    this.createArrowMarker();

    if (this.graphData.nodes.length > 0) {
      this.createSimulation(width, height, true);
    }
  }

  renderGraph() {
    if (!this.svg) return;

    this.svg.selectAll('*').remove();

    this.createArrowMarker();

    if (this.graphData.nodes.length === 0) {
      this.svg.append('text')
        .attr('x', '50%')
        .attr('y', '50%')
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .style('font-size', '16px')
        .style('fill', '#666')
        .text('No database relationships found');
      return;
    }

    const svgNode = this.svg.node();
    const width = svgNode ? svgNode.getBoundingClientRect().width : 800;
    const height = svgNode ? svgNode.getBoundingClientRect().height : 600;

    const centerX = width / 2;
    const centerY = height / 2;
    const nodesCount = this.graphData.nodes.length;
    const radius = Math.min(width, height) / 2 - 50;
    this.graphData.nodes.forEach((node: any, index: number) => {
      const angle = 2 * Math.PI * index / nodesCount;
      node.x = centerX + radius * Math.sin(angle);
      node.y = centerY + radius * Math.cos(angle);
    });

    const link = this.svg.append('g')
      .selectAll('line')
      .data(this.graphData.links)
      .enter().append('line')
      .attr('stroke', '#999')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', 2)
      .attr('marker-end', 'url(#arrowhead)');

    const node = this.svg.append('g')
      .selectAll('g')
      .data(this.graphData.nodes)
      .enter().append('g')
      .attr('class', 'node')
      .call((selection: any) => {
        selection.on('click', (event: any, d: any) => this.handleNodeClick(event, d));
      });

    node.append('circle')
      .attr('r', 35)
      .attr('fill', (d: any) => this.color(d.id))
      .attr('stroke', '#fff')
      .attr('stroke-width', 3);

    node.append('text')
      .text((d: any) => d.name)
      .attr('text-anchor', 'middle')
      .attr('dy', '.35em')
      .style('font-size', '12px')
      .style('font-weight', 'bold')
      .style('fill', '#fff')
      .style('text-shadow', '1px 1px 2px rgba(0,0,0,0.8), -1px -1px 2px rgba(0,0,0,0.8), 1px -1px 2px rgba(0,0,0,0.8), -1px 1px 2px rgba(0,0,0,0.8)')
      .style('pointer-events', 'none');

    node.append('title')
      .text((d: any) => `Table: ${d.name}\nClick to view details\nCtrl+Click to select (orange margin)`);

    this.svg.on('click', (event: any) => {
      if (event.target === this.svg.node()) {
        this.clearSelection();
      }
    });

    this.createSimulation(width, height, false);

    this.simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => {
          const x = d.source.x;
          return this.isValidNumber(x) ? Math.max(0, Math.min(width, x)) : 0;
        })
        .attr('y1', (d: any) => {
          const y = d.source.y;
          return this.isValidNumber(y) ? Math.max(0, Math.min(height, y)) : 0;
        })
        .attr('x2', (d: any) => {
          const x = d.target.x;
          return this.isValidNumber(x) ? Math.max(0, Math.min(width, x)) : 0;
        })
        .attr('y2', (d: any) => {
          const y = d.target.y;
          return this.isValidNumber(y) ? Math.max(0, Math.min(height, y)) : 0;
        });

      node
        .attr('transform', (d: any) => {
          const x = d.x;
          const y = d.y;
          
          if (!this.isValidNumber(x) || !this.isValidNumber(y)) {
            d.x = width / 2;
            d.y = height / 2;
            return `translate(${width / 2},${height / 2})`;
          }
          
          const boundedX = Math.max(50, Math.min(width - 50, x));
          const boundedY = Math.max(50, Math.min(height - 50, y));
          
          if (boundedX !== x) {
            d.x = boundedX;
          }
          if (boundedY !== y) {
            d.y = boundedY;
          }
          
          return `translate(${boundedX},${boundedY})`;
        });
    });

    node.call((selection: any) => {
      const widget = this;
      selection.on('mouseover', function(event: any, d: any) {
        const isSelected = widget.selectedNodes.has(d.id);
        
        d3_select(this).select('circle')
          .attr('stroke-width', isSelected ? 6 : 4)
          .attr('stroke', isSelected ? '#ff8c00' : '#333');
        
        link
          .attr('stroke-opacity', (linkData: any) => {
            const sourceId = typeof linkData.source === 'object' ? linkData.source.id : linkData.source;
            const targetId = typeof linkData.target === 'object' ? linkData.target.id : linkData.target;
            return (sourceId === d.id || targetId === d.id) ? 1 : 0.1;
          })
          .attr('stroke-width', (linkData: any) => {
            const sourceId = typeof linkData.source === 'object' ? linkData.source.id : linkData.source;
            const targetId = typeof linkData.target === 'object' ? linkData.target.id : linkData.target;
            return (sourceId === d.id || targetId === d.id) ? 3 : 2;
          })
          .attr('stroke', (linkData: any) => {
            const sourceId = typeof linkData.source === 'object' ? linkData.source.id : linkData.source;
            const targetId = typeof linkData.target === 'object' ? linkData.target.id : linkData.target;
            return (sourceId === d.id || targetId === d.id) ? '#87CEEB' : '#999';
          });
        
        node.select('circle')
          .attr('stroke-width', (nodeData: any) => {
            const isConnected = link.data().some((linkData: any) => {
              const sourceId = typeof linkData.source === 'object' ? linkData.source.id : linkData.source;
              const targetId = typeof linkData.target === 'object' ? linkData.target.id : linkData.target;
              return (sourceId === d.id && targetId === nodeData.id) || 
                     (targetId === d.id && sourceId === nodeData.id);
            });
            const isNodeSelected = widget.selectedNodes.has(nodeData.id);
            return isNodeSelected ? 6 : (isConnected ? 4 : 3);
          })
          .attr('stroke', (nodeData: any) => {
            const isConnected = link.data().some((linkData: any) => {
              const sourceId = typeof linkData.source === 'object' ? linkData.source.id : linkData.source;
              const targetId = typeof linkData.target === 'object' ? linkData.target.id : linkData.target;
              return (sourceId === d.id && targetId === nodeData.id) || 
                     (targetId === d.id && sourceId === nodeData.id);
            });
            const isNodeSelected = widget.selectedNodes.has(nodeData.id);
            return isConnected ? '#87CEEB' : (isNodeSelected ? '#ff8c00' : '#fff');
          });
      })
      .on('mouseout', function() {
        widget.updateSelection();
        
        link
          .attr('stroke-opacity', 0.6)
          .attr('stroke-width', 2)
          .attr('stroke', '#999');
      });
    });

    node.call(drag()
      .on('start', (event: any, d: any) => {
        if (!event.active) this.simulation.alphaTarget(0.3).restart();
        d.fx = this.isValidNumber(d.x) ? d.x : width / 2;
        d.fy = this.isValidNumber(d.y) ? d.y : height / 2;
      })
      .on('drag', (event: any, d: any) => {
        const boundedX = Math.max(50, Math.min(width - 50, event.x));
        const boundedY = Math.max(50, Math.min(height - 50, event.y));
        d.fx = boundedX;
        d.fy = boundedY;
      })
      .on('end', (event: any, d: any) => {
        if (!event.active) this.simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      }));
  }

  private isValidNumber(value: any): boolean {
    return typeof value === 'number' && !isNaN(value) && isFinite(value);
  }

  private toggleSelection(nodeId: string): void {
    if (this.selectedNodes.has(nodeId)) {
      this.selectedNodes.delete(nodeId);
    } else {
      this.selectedNodes.add(nodeId);
    }
    this.updateSelection();
  }

  private clearSelection(): void {
    this.selectedNodes.clear();
    this.updateSelection();
  }

  private updateSelection(): void {
    if (!this.svg) return;

    const widget = this;
    this.svg.selectAll('.node').each(function(d: any) {
      const nodeElement = d3_select(this);
      const isSelected = widget.selectedNodes.has(d.id);
      
      nodeElement.select('circle')
        .attr('stroke', isSelected ? '#ff8c00' : '#fff')
        .attr('stroke-width', isSelected ? 6 : 3)
        .attr('stroke-dasharray', 'none');
    });

    const newQueryBtn = this.node.querySelector('#new-query-btn') as HTMLElement;
    const clearBtn = this.node.querySelector('#clear-selection-btn') as HTMLElement;
    
    if (!newQueryBtn || !clearBtn) return;

    if (this.selectedNodes.size > 0) {
      newQueryBtn.innerHTML = `<i class="fa fa-plus" style="margin-right:4px;"></i> New Query <span style="background:#ff8c00;color:white;padding:2px 6px;border-radius:10px;font-size:11px;margin-left:4px;">${this.selectedNodes.size}</span>`;
      clearBtn.style.display = 'inline-block';
    } else {
      newQueryBtn.innerHTML = '<i class="fa fa-plus" style="margin-right:4px;"></i> New Query';
      clearBtn.style.display = 'none';
    }
  }

  private handleNodeClick(event: any, d: any): void {
    if (event.ctrlKey || event.metaKey) {
      event.preventDefault();
      event.stopPropagation();
      this.toggleSelection(d.id);
    } else {
      this.openTableInfoTab(d.name);
    }
  }

  getSelectedTables(): string[] {
    return Array.from(this.selectedNodes);
  }

  selectTables(tableNames: string[]): void {
    tableNames.forEach(name => {
      this.selectedNodes.add(name);
    });
    this.updateSelection();
  }

  renderTableList(tables: string[]) {
    const dropdownMenu = this.node.querySelector('#tables-dropdown') as HTMLElement;
    if (!dropdownMenu) {
      console.error('Tables dropdown element not found in renderTableList');
      return;
    }
    const d3menu = d3_select(dropdownMenu);
    d3menu.html('');
    
    if (!tables || tables.length === 0) {
      d3menu.append('div')
        .text('No tables found.')
        .style('padding', '0.5rem')
        .style('color', '#666')
        .style('font-style', 'italic');
      return;
    }

    d3menu.append('div')
      .text(`Tables (${tables.length})`)
      .style('font-weight', 'bold')
      .style('padding', '0.5rem')
      .style('border-bottom', '1px solid #eee')
      .style('margin-bottom', '0.5rem');

    tables.forEach(tableName => {
      const item = d3menu.append('div')
        .style('padding', '0.5rem')
        .style('cursor', 'pointer')
        .style('border-radius', '3px')
        .style('margin-bottom', '0.25rem')
        .style('transition', 'background-color 0.2s')
        .on('mouseover', function() {
          d3_select(this).style('background-color', '#f8f9fa');
        })
        .on('mouseout', function() {
          d3_select(this).style('background-color', 'transparent');
        })
        .on('click', () => {
          this.openTableInfoTab(tableName);
          dropdownMenu.style.display = 'none';
          const dropdownButton = this.node.querySelector('[data-toggle="dropdown"]');
          if (dropdownButton) {
            dropdownButton.setAttribute('aria-expanded', 'false');
          }
        });

      item.append('i')
        .classed('fa fa-table', true)
        .style('margin-right', '0.5rem')
        .style('color', '#007bff');

      item.append('span')
        .text(tableName)
        .style('font-size', '14px');
    });
  }

  async openTableInfoTab(tableName: string) {
    let widget: Widget | null = null;
    try {
      const response = await fetch(`/db/table/${encodeURIComponent(tableName)}`);
      if (!response.ok) throw new Error('Failed to fetch table details');
      const details = await response.json();
      widget = new TableInfoWidget(tableName, details);
    } catch (e) {
      widget = new DatabaseTabWidget();
      widget.title.label = tableName;
      widget.node.innerHTML = `<div style="color: red; padding: 10px;">Error loading table info: ${e.message}</div>`;
    }

    let refWidget: Widget | null = null;
    if(this.panel.widgets) {
      for (let w of this.panel.widgets()) {
        if (w instanceof TableInfoWidget || w instanceof QueryResultWidget) {
          refWidget = w;
        }
      }
    }
    if (refWidget) {
      this.panel.addInfoWidget(widget, { ref: refWidget, mode: 'tab-after' });
    } else {
      this.panel.addInfoWidget(widget, { ref: this, mode: 'split-bottom' });
    }
    this.panel.activateWidget(widget);
  }

  protected onResize(msg: Widget.ResizeMessage): void {
    if (this.graphData.nodes.length > 0) {
      this.initializeGraph();
      this.renderGraph();
    }
  }

  private getInitialQuery(selectedTables: string[]): string {
    if (selectedTables.length === 0) 
      return '';
    
    if (selectedTables.length === 1) {
      return `SELECT * FROM "${selectedTables[0]}" LIMIT 100;`;
    }
    
    let initialQuery = `SELECT *\nFROM "${selectedTables[0]}"\n`;
    
    const usedTables = new Set([selectedTables[0]]);
    const joins: string[] = [];
    
    for (let i = 1; i < selectedTables.length; i++) {
      const currentTable = selectedTables[i];
      let joinFound = false;
      
      for (const link of this.graphData.links) {
        console.log(link.source, link.target);
        const sourceTable = (link.source as TableNode).id;
        const targetTable = (link.target as TableNode).id;
        
        if (sourceTable === currentTable && usedTables.has(targetTable)) {
          joins.push(`JOIN "${currentTable}" ON "${targetTable}".${link.targetColumn} = "${currentTable}".${link.sourceColumn}`);
          usedTables.add(currentTable);
          joinFound = true;
          break;
        }
        
        if (targetTable === currentTable && usedTables.has(sourceTable)) {
          joins.push(`JOIN "${currentTable}" ON "${sourceTable}".${link.sourceColumn} = "${currentTable}".${link.targetColumn}`);
          usedTables.add(currentTable);
          joinFound = true;
          break;
        }
      }
      
      if (!joinFound) {
        joins.push(`CROSS JOIN "${currentTable}"`);
        usedTables.add(currentTable);
      }
    }
    
    return initialQuery + joins.join('\n') + '\nLIMIT 100;';
  }

  private async openNewQueryTab(): Promise<void> {
    const selectedTables = this.getSelectedTables();
    const tableNames = this.graphData.nodes.map(n => n.name);
    const initialQuery = this.getInitialQuery(selectedTables);
    
    let columnNames: string[] = [];
    if (selectedTables.length > 0) {
      try {
        const columnPromises = selectedTables.map(async (tableName) => {
          const response = await fetch(`/db/table/${encodeURIComponent(tableName)}`);
          if (response.ok) {
            const details = await response.json();
            return details.columns ? details.columns.map((col: any) => col.name) : [];
          }
          return [];
        });
        
        const columnArrays = await Promise.all(columnPromises);
        columnNames = [].concat(...columnArrays);
      } catch (error) {
        console.warn('Failed to fetch column names:', error);
      }
    }
    
    const queryWidget = new QueryWidget(this.panel, tableNames, columnNames, initialQuery);
    
    this.panel.addInfoWidget(queryWidget, { ref: this, mode: 'tab-after' });
    this.panel.activateWidget(queryWidget);
    
    this.clearSelection();
  }
} 
