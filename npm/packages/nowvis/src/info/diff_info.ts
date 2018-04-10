import {
  select as d3_select,
  Selection as d3_Selection,
  BaseType as d3_BaseType,
} from 'd3-selection';

import {Widget} from '@phosphor/widgets';

import {json} from '@noworkflow/utils';


import {
  ModuleData, FileAccessData, EnvironmentItemData,
  DiffInfoData, DiffModuleData, DiffEnvironmentData, DiffAccessData,
  FilterObject
} from './structures';

import {ModulesInfoWidget} from './modules_info';
import {EnvironmentInfoWidget} from './environment_info';
import {FileAccessesInfoWidget} from './file_accesses_info';
import {TrialInfoWidget} from './trial_info';

export
class DiffInfoWidget extends Widget {

  d3node: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>;
  display1: string;
  display2: string;

  static url(trial1: string, trial2: string) {
    return ("diff/"
      + trial1 + "/" + trial2 + "/info.json"
    );
  }

  static modules_url(trial1: string, trial2: string) {
    return ("diff/"
      + trial1 + "/" + trial2 + "/dependencies.json"
    );
  }

  static environment_url(trial1: string, trial2: string) {
    return ("diff/"
      + trial1 + "/" + trial2 + "/environment.json"
    );
  }

  static accesses_url(trial1: string, trial2: string) {
    return ("diff/"
      + trial1 + "/" + trial2 + "/file_accesses.json"
    );
  }

  static createNode(): HTMLElement {
    let node = document.createElement('div');
    let d3node = d3_select(node);

    d3node.append('div')
      .classed('trial-info', true)

    return node;
  }

  constructor(display1:string, display2: string, trial1: string, trial2: string) {
    super({ node: DiffInfoWidget.createNode() });
    this.display1 = display1;
    this.display2 = display2;
    this.d3node = d3_select(this.node);
    this.addClass('content');
    this.addClass('trial-info');
    this.title.label = display1 + "<->" + display2 + " - Diff Info";
    this.title.closable = true;
    this.title.caption = `Diff ${display1}-${display2} Information`;
    this.load(trial1, trial2);
  }

  load(trial1: string, trial2: string) {
    let sub = this.node.getElementsByClassName("trial-info")[0];
    json("Info", sub, DiffInfoWidget.url(trial1, trial2), (data: DiffInfoData) => {
      this.createMain(data);
      this.loadModules(trial1, trial2);
      this.loadEnvironment(trial1, trial2);
      this.loadFileAccess(trial1, trial2);
    })
  }

  createMain(data: DiffInfoData) {
    let trial = data.trial;
    let trial1 = data.trial1;
    let trial2 = data.trial2;

    let content = this.d3node.select('.trial-info').html("")
    .append('div')
      .classed('side-info', true)
    let main = content.append('div')
      .classed('main', true)

    let h1 = main.append("h1")

    // Title
    h1.append("span")
      .classed("dbefore", true)
      .text("Trial " + this.display1);

    h1.append("span")
      .text(" <-> ");

    h1.append("span")
      .classed("dafter", true)
      .text("Trial " + this.display2);

    // Code hash
    if (trial.code_hash == undefined) {
      main.append("h3")
        .classed("hash", true)
        .text(trial1.code_hash || "");
    } else {
      main.append("h3")
        .classed("hash dbefore", true)
        .text(trial1.code_hash || "");
      main.append("h3")
        .classed("hash dafter", true)
        .text(trial2.code_hash || "");
    }
    this.info(main, "id", "Id", trial1.id, trial2.id);
    this.info(main, "script", "Script", trial1.script, trial2.script);
    this.info(main, "start", "Start", trial1.start, trial2.start);
    this.info(main, "finish", "Finish", trial1.finish, trial2.finish);
    this.info(main, "duration", "Duration", trial1.duration_text, trial2.duration_text);


    if (trial.arguments == undefined) {
      if (trial1.arguments) {
        let attr = main.append("span")
          .classed("attr", true);
        attr.append("span")
          .classed("desc", true)
          .text("Arguments: ");
        attr.append("span")
          .classed("arguments", true)
          .text(trial1.arguments);
      }
    } else {
      if (trial1.arguments) {
        let attr = main.append("span")
          .classed("attr", true);
        attr.append("span")
          .classed("desc dbefore", true)
          .text("Arguments: ");
        attr.append("span")
          .classed("arguments", true)
          .text(trial1.arguments);
      }
      if (trial2.arguments) {
        let attr = main.append("span")
          .classed("attr", true);
        attr.append("span")
          .classed("desc dafter", true)
          .text("Arguments: ");
        attr.append("span")
          .classed("arguments", true)
          .text(trial2.arguments);
      }
    }

    content.append("div")
      .classed("modules", true);

    content.append("div")
      .classed("environment", true)

    content.append("div")
      .classed("file-accesses", true)
  }

  filter_trial(filter: FilterObject, filterfn: (strial: number) => void) {
    let select_trial = filter.filterdiv.append("select");
    select_trial.append("option")
      .attr("value", "3")
      .text("Do not filter Trial");

    select_trial.append("option")
      .attr("value", "1")
      .text("First Trial Only");

    select_trial.append("option")
      .attr("value", "5")
      .text("Exists in First Trial");

    select_trial.append("option")
      .attr("value", "2")
      .text("Second Trial Only");

    select_trial.append("option")
      .attr("value", "6")
      .text("Exists in Second Trial");

    select_trial.append("option")
      .attr("value", "4")
      .text("Both Trials Only");
    select_trial.property("value", "3");

    let newfilter = () => {
      filterfn(Number(select_trial.property("value")));
    }
    select_trial.on("change", newfilter);
    filter.on_change(newfilter);
  }

  loadModules(trial1: string, trial2: string) {
    let sub = this.node.getElementsByClassName("modules")[0];

    json("Modules", sub, DiffInfoWidget.modules_url(trial1, trial2), (data: DiffModuleData) => {
      let modules = this.d3node.select(".modules").html("");
      if ((data.modules_added.length > 0) ||
          (data.modules_removed.length > 0) ||
          (data.modules_replaced.length > 0)) {
        let fold = TrialInfoWidget.createFold(modules, "Modules");
        let foldable = modules.append("div").classed("foldable show-toolbar", true);
        let filter = ModulesInfoWidget.createFilter(foldable);
        let ul = foldable.append("ul")
          .classed("mod-list", true)
        this.filter_trial(filter, (strial: number) => {
          ul.html("");
          if ((strial & 1) == 1) {
            for (var element of data.modules_removed) {
              if (!filter.valid(data.t1_path, element)) {
                continue;
              }
              this.mod_li(ul, 'libefore', element);
            }
          }
          if ((strial & 2) == 2) {
            for (var element of data.modules_added) {
              if (!filter.valid(data.t2_path, element)) {
                continue;
              }
              this.mod_li(ul, 'liafter', element);
            }
          }
          if (strial >= 3) {
            for (var elements of data.modules_replaced) {
              let rem = elements[0],
                  add = elements[1];
              if (!filter.valid(data.t1_path, rem) ||
                  !filter.valid(data.t2_path, add)) {
                continue;
              }
              let li = ul.append("li")

              li.append("div")
                .classed("name", true)
                .text(rem.name);

              let version = li.append("div")
                .classed("version", true)
              version.append("div")
                .classed("dbefore", true)
                .text(rem.version)
              version.append("div")
                .classed("dafter", true)
                .text(add.version)

              li.append("div")
                .classed("clear", true)

              li.append("div")
                .classed("hash dbefore", true)
                .attr("title", rem.path)
                .text(rem.code_hash);

              li.append("div")
                .classed("hash dafter", true)
                .attr("title", add.path)
                .text(add.code_hash);
            }
          }
        });
        TrialInfoWidget.createFilterFold(fold, filter);
      }
    });
  }

  loadEnvironment(trial1: string, trial2: string) {
    let sub = this.node.getElementsByClassName("environment")[0];

    json("Environment", sub, DiffInfoWidget.environment_url(trial1, trial2), (data: DiffEnvironmentData) => {
      let environment = this.d3node.select(".environment").html("");
      if ((data.env_added.length > 0) ||
          (data.env_removed.length > 0) ||
          (data.env_replaced.length > 0)) {
        let fold = TrialInfoWidget.createFold(environment, "Environment");
        let foldable = environment.append("div").classed("foldable show-toolbar", true);
        let filter = EnvironmentInfoWidget.createFilter(foldable);
        let ul = foldable.append("ul")
          .classed("env-list", true)
        this.filter_trial(filter, (strial: number) => {
          ul.html("");
          if ((strial & 1) == 1) {
            for (var element of data.env_removed) {
              if (!filter.valid(element)) {
                continue;
              }
              this.env_li(ul, 'dbefore', element);
            }
          }
          if ((strial & 2) == 2) {
            for (var element of data.env_added) {
              if (!filter.valid(element)) {
                continue;
              }
              this.env_li(ul, 'dafter', element);
            }
          }
          if (strial >= 3) {
            for (var elements of data.env_replaced) {
              let rem = elements[0],
                  add = elements[1];
              if (!filter.valid(rem) ||
                  !filter.valid(add)) {
                continue;
              }
              this.env_cli(ul, rem, add);
            }
          }
        });
        TrialInfoWidget.createFilterFold(fold, filter);
      }
    })
  }

  loadFileAccess(trial1: string, trial2: string) {
    let sub = this.node.getElementsByClassName("file-accesses")[0];

    json("File Accesses", sub, DiffInfoWidget.accesses_url(trial1, trial2), (data: DiffAccessData) => {
      let accesses = this.d3node.select(".file-accesses").html("");
      if ((data.fa_added.length > 0) ||
          (data.fa_removed.length > 0) ||
          (data.fa_replaced.length > 0)) {
        let fold = TrialInfoWidget.createFold(accesses, "File Accesses");
        let foldable = accesses.append("div").classed("foldable show-toolbar", true);
        let filter = FileAccessesInfoWidget.createFilter(foldable);
        let ul = foldable.append("ul")
          .classed("fac-list", true)
        this.filter_trial(filter, (strial: number) => {
          ul.html("");

          if ((strial & 1) == 1) {
            for (var element of data.fa_removed) {
              if (!filter.valid(data.t1_path, element)) {
                continue;
              }
              this.fa_li(ul, 'libefore', element);
            }
          }
          if ((strial & 2) == 2) {
            for (var element of data.fa_added) {
              if (!filter.valid(data.t2_path, element)) {
                continue;
              }
              this.fa_li(ul, 'liafter', element);
            }
          }
          if (strial >= 3) {
            for (var elements of data.fa_replaced) {
              let rem = elements[0],
                  add = elements[1];
              if (!filter.valid(data.t1_path, rem) ||
                  !filter.valid(data.t2_path, add)) {
                continue;
              }
              let li = ul.append("li")

              this.fa_cfield(li, 'name', 'Name', rem.name, add.name);
              this.fa_cfield(li, 'mode', 'Mode', rem.mode, add.mode);
              this.fa_cfield(li, 'buffering', 'Buffering', rem.buffering, add.buffering);
              li.append("div")
                .classed("clear", true)
              this.fa_cfield(li, 'timestamp', 'Time', rem.timestamp, add.timestamp);
              this.fa_cfield(li, 'content_hash_before hash', 'Content hash before', rem.content_hash_before, add.content_hash_before);
              this.fa_cfield(li, 'content_hash_after hash', 'Content hash after', rem.content_hash_after, add.content_hash_after);
              this.fa_cfield(li, 'stack', 'Stack', rem.stack, add.stack);
            }
          }
        });
        TrialInfoWidget.createFilterFold(fold, filter);
      }
    });
  }

  private info(main: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, cls: string, label: string, value1: any, value2: any) {
    if (value1 == value2) {
      let attr = main.append("span")
        .classed("attr", true);
      attr.append("span")
        .classed("desc", true)
        .text(label + ": ");
      attr.append("span")
        .classed(cls, true)
        .text(value1);
    } else {
      let attr1 = main.append("span")
        .classed("attr dbefore", true);
      attr1.append("span")
        .classed("desc", true)
        .text(label + ": ");
      attr1.append("span")
        .classed(cls, true)
        .text(value1);

      let attr2 = main.append("span")
        .classed("attr dafter", true);
      attr2.append("span")
        .classed("desc", true)
        .text(label + ": ");
      attr2.append("span")
        .classed(cls, true)
        .text(value2);
    }
  }

  private mod_li(element: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, cls: string, mod: ModuleData) {
    let li = element.append("li")
      .classed(cls, true);

    li.append("div")
      .classed("name", true)
      .text(mod.name);

    li.append("div")
      .classed("version", true)
      .text(mod.version);

    li.append("div")
      .classed("clear", true)

    li.append("div")
      .classed("hash", true)
      .attr("title", mod.path)
      .text(mod.code_hash);
  }

  private env_field(element: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, env: EnvironmentItemData) {
    element.append("span")
      .classed("key", true)
      .text(env.name);

    element.append("span")
      .classed("equal", true)
      .text(" = ");

    element.append("span")
      .classed("value", true)
      .text(env.value);

  }

  private env_li(element: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, cls: string, env: EnvironmentItemData) {
    this.env_field(
      element.append("li")
        .classed(cls, true),
      env
    )
  }

  private env_cli(element: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, rem: EnvironmentItemData, add: EnvironmentItemData) {
    let li = element.append("li");
    this.env_field(
      li.append("div")
        .classed("dbefore", true),
      rem
    )
    this.env_field(
      li.append("div")
        .classed("dafter", true),
      add
    )
  }

  private fa_field(element: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, cls: string, title: string, value: string) {
    element.append("div")
      .classed(cls, true)
      .attr("title", title)
      .text(value);
  }

  private fa_li(element: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, cls: string, fa: FileAccessData) {
    let li = element.append("li")
      .classed(cls, true);

    this.fa_field(li, 'name', 'Name', fa.name);
    this.fa_field(li, 'mode', 'Mode', fa.mode);
    this.fa_field(li, 'buffering', 'Buffering', fa.buffering);

    li.append("div")
      .classed("clear", true)

    this.fa_field(li, 'timestamp', 'Time', fa.timestamp);
    this.fa_field(li, 'content_hash_before hash', 'Content hash before', fa.content_hash_before);
    this.fa_field(li, 'content_hash_after hash', 'Content hash after', fa.content_hash_after);
    this.fa_field(li, 'stack', 'Stack', fa.stack);
  }

  private fa_cfield(element: d3_Selection<d3_BaseType, {}, HTMLElement | null, any>, cls: string, title: string, v1: string, v2: string) {
    if (v1 == v2) {
      this.fa_field(element, cls, title, v1);
    } else {
      this.fa_field(element, cls + " dbefore", title, v1);
      this.fa_field(element, cls + " dafter", title, v2);
    }
  }

}
