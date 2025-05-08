import {
    select as d3_select,
    Selection as d3_Selection,
    BaseType as d3_BaseType,
  } from 'd3-selection';

import {NowVisPanel} from '../nowpanel';
import {Widget} from '@lumino/widgets';

export function functionDiffWindow(functionDiffJson : any, windowIdAndTitle:string, parentDock : NowVisPanel){   
    if(document.getElementById(windowIdAndTitle)){
        alert("This function diff is already open!")
        return
    }
    
    let functionDiffWidget = new Widget();
    functionDiffWidget.title.label = windowIdAndTitle
    functionDiffWidget.id = windowIdAndTitle;
    functionDiffWidget.title.closable = true;
    parentDock.addGraphWidget(functionDiffWidget);
    parentDock.activateWidget(functionDiffWidget);

    let functionDiffWindow = d3_select(document.getElementById(windowIdAndTitle));
    functionDiffWindow.style("overflow-y", "auto").style("padding", "2em 2em 2em 1em");

    function addHideShowButton(elementToAppendTo : any, buttonId : string, spanId : string){
      buttonId += "-" + crypto.randomUUID();
      return elementToAppendTo.append("span").append("i").attr("id", buttonId).classed("fa fa-compress", true).on("click",()=>{
        let spanToHideOrShow = d3_select(document.getElementById(spanId));
        let thisButton = d3_select(document.getElementById(buttonId));
        if(spanToHideOrShow.classed("d-none")){
          spanToHideOrShow.classed("d-none", false);
          thisButton.classed("fa fa-expand", false);
          thisButton.classed("fa fa-compress", true);
        }else{
          spanToHideOrShow.classed("d-none", true);
          thisButton.classed("fa fa-compress", false);
          thisButton.classed("fa fa-expand", true);
        }
      });
    }

    function filterVariablesArray(array : any, opVariables: boolean){
      
      let defaultVariables: any[] = ["name", "attribute", "access"];
      if(opVariables) defaultVariables =  defaultVariables.concat(["add", "sub", "mult", "div", "mod", "pow", "floordiv", // arithmetic operators
              "add_assign", "sub_assign", "mult_assign", "div_assign", // assignment operators 1
              "mod_assign", "pow_assign", "floordiv_assign", // assignment operators 2
              "bitand_assign", "bitor_assign", "bitxor_assign", // assignment operators 3
              "rshift_assign", "lshift_assign", // assignment operators 4
              "eq", "noteq", "gt", "lt", "gte", "lte", // comparison operators
              "and", "or", "not", // logical operators
              "is", "isnot", // identity operators
              "in", "notin", // membership operators
              "bitand", "bitor", "bitxor", "invert", "rshift", "lshift"]); // bitwise operators]

      

      let filteredArray = array.filter((arrayElement : string)=>{

        for(let i = 0; i < defaultVariables.length; i++){
          if(arrayElement.includes("'type': '"+defaultVariables[i]+"',")) return true;
        }

        return false;
      });

      return filteredArray;

    }

    function writeHTMLDiffVariables(spanVariables: d3_Selection<HTMLSpanElement, unknown, null, undefined>, trial1VariablesThatChanged: any[], trial2VariablesAdded: any[], trial1VariablesRemoved : any[]) {

      if(trial1VariablesThatChanged.length > 0){

        let variablesChangedTitle = spanVariables.append("p").attr("style","font-weight:bold;").text("The variables changed:");
        let spanVariablesChanged = spanVariables.append("spand").attr("id", "diff-function-variables-changed-span-" + crypto.randomUUID());
        addHideShowButton(variablesChangedTitle, "hide-and-show-button-variables-changed", spanVariablesChanged.attr("id"));

        trial1VariablesThatChanged.forEach((diffVar: any) => {
          let variablesLines = diffVar.match(/\{[^}]*\}/g);
          let differentAttributes = findDifferenceBetweenVariables(variablesLines[0], variablesLines[1]);

          spanVariablesChanged.append("span").html(colorJsonAttributesHTML(variablesLines[0], differentAttributes, "red"));
          spanVariablesChanged.append("br");
          spanVariablesChanged.append("span").html(colorJsonAttributesHTML(variablesLines[1], differentAttributes, "green"));
          spanVariablesChanged.append("br");
          spanVariablesChanged.append("br");
        });
      }

      if (trial2VariablesAdded.length > 0) {
        let variablesAddedTitle = spanVariables.append("p").attr("style", "font-weight:bold;").text("The variables added:");
        let spanVariablesAdded = spanVariables.append("spand").attr("id", "diff-function-variables-added-span-"+crypto.randomUUID());
        addHideShowButton(variablesAddedTitle, "hide-and-show-button-variables-added", spanVariablesAdded.attr("id"));

        trial2VariablesAdded.forEach((varAdded: any) => {
          spanVariablesAdded.append("span").style("color", "green").text(varAdded);
          spanVariablesAdded.append("br");
        });
      }

      if (trial1VariablesRemoved.length > 0) {
        let variablesRemovedTitle = spanVariables.append("p").attr("style", "font-weight:bold;").text("The variables removed:");
        let spanVariablesRemoved = spanVariables.append("spand").attr("id", "diff-function-variables-removed-span"+crypto.randomUUID());
        addHideShowButton(variablesRemovedTitle, "hide-and-show-button-removed-added", spanVariablesRemoved.attr("id"));

        trial1VariablesRemoved.forEach((varRemoved: any) => {
          spanVariablesRemoved.append("span").style("color", "red").text(varRemoved);
          spanVariablesRemoved.append("br");
        });
      }
    }


    function findDifferenceBetweenVariables(variable1 : string, variable2 : string){
      let jsonVariable1 = JSON.parse(variable1.replace(/"'/g,"\"").replace(/'"/g,"\"").replace(/'/g,"\""));
      let jsonVariable2 = JSON.parse(variable2.replace(/"'/g,"\"").replace(/'"/g,"\"").replace(/'/g,"\""));
  
      let differentAttributes = []
      for(let attr in jsonVariable1){
        if (jsonVariable1[attr] != jsonVariable2[attr]) differentAttributes.push(attr.toString());
      }
  
      return differentAttributes;
    }
  
    function colorJsonAttributesHTML(jsonAsString : string, attributesArray : any, color : string) : string{
      let coloredJsonAsString = jsonAsString.replace(/'<([^>]+)>'/g, "'$1'");
      attributesArray.forEach((attr : string)=>{
        // Annotated code = color only the attribute
        //attr = "'"+attr+"':";
        //coloredJsonAsString = coloredJsonAsString.replace(attr, "<span style=\"color: "+color+";\">" + attr + "</span>");
        let regex = "'"+attr+"':"+"(.*?),"
        let regexMatches = coloredJsonAsString.match(new RegExp(String.raw`\s${regex}\s`))!;
        coloredJsonAsString = coloredJsonAsString.replace(regexMatches[1], "<span style=\"color: "+color+";\">" + regexMatches[1] + "</span>");
      });
      return coloredJsonAsString;
    }

    function colorArrayElementsHTML(array : any, symDifference : any, color : string){
      let coloredArray = array;
      symDifference.forEach((argument: any) => { 
        if (coloredArray.includes(argument)) coloredArray[coloredArray.indexOf(argument)] = "<span style=\"color: "+color+"\">" + argument.toString() + "</span>"; 
      });
      return coloredArray.toString();
    }

    function writeFileAccess(fileAccessArray : any, window : any, color : string){
      fileAccessArray.forEach((file:any)=>{
        window.append("span").style("color", color).text("Name: " + file.name);
        window.append("br");
        window.append("span").style("color", color).text("Mode: " + file.mode);
        window.append("br");
        window.append("span").style("color", color).text(" Buffering: " + file.buffering);
        window.append("br");
        window.append("span").style("color", color).text("Content hash before: " + file.content_hash_before).on("click", () => {
          downloadFileContent(file.content_hash_before, file.name);
        });
        window.append("br");
        window.append("span").style("color", color).text("Content hash after: " + file.content_hash_after).on("click", () => {
          downloadFileContent(file.content_hash_after, file.name);
        });
        window.append("br");
        window.append("span").style("color", color).text("Timestamp: " + file.timestamp);
        window.append("br");
        window.append("span").style("color", color).text("Function: " + file.stack);
        window.append("br");
        window.append("br");
      });
    }
    
    ["output", "arguments", "duration", "variables"].forEach((property)=>{
      let didntChange = JSON.stringify(functionDiffJson[property+"_function_trial1"]) == JSON.stringify(functionDiffJson[property+"_function_trial2"]);
      let changeText = didntChange ? "The " + property + " didn't change" : "The " + property + " changed:";
      let textChangeTitle;
      if(property != "variables") textChangeTitle = functionDiffWindow.append("p").attr("style","font-weight:bold;").text(changeText);

      if(changeText.includes("changed")){
        if(property == "duration"){
          functionDiffJson[property+"_function_trial1"] = functionDiffJson[property+"_function_trial1"].toString() + " miliseconds"
          functionDiffJson[property+"_function_trial2"] = functionDiffJson[property+"_function_trial2"].toString() + " miliseconds"
        }

        let spanProperty = functionDiffWindow.append("span").attr("id", "diff-function-"+property+"-span-"+crypto.randomUUID());

        if(property != "variables") addHideShowButton(textChangeTitle, "hide-and-show-button-"+property, spanProperty.attr("id"));
        
        if(property == "variables"){

          let buttonDiv = functionDiffWindow.append("div").attr("id", "div-diff-function-variables-filter").lower();
          
          buttonDiv.append("span")
            .classed("toollink", true)
            .attr("id", "filter-" + windowIdAndTitle + "-variables-default")
            .attr("href", "#")
            .attr("title", "Show only name, attribute, and access variables")
            .on("click", () => {
              
              let trial1ChangedVariablesFiltered = filterVariablesArray(functionDiffJson["trial1_variables_that_changed"], false);
              let trial2AddedVariablesFiltered = filterVariablesArray(functionDiffJson["trial2_variables_added"], false);
              let trial1RemovedVariablesFiltered = filterVariablesArray(functionDiffJson["trial1_variables_removed"], false);

              spanProperty.html("");
              writeHTMLDiffVariables(spanProperty, trial1ChangedVariablesFiltered, trial2AddedVariablesFiltered, trial1RemovedVariablesFiltered);

            })
            .append("i")
            .classed("fa fa-asterisk", true).append("span").style("margin-right","10px").text("Show only name, attribute, and access variables");

          buttonDiv.append("span")
          .classed("toollink", true)
          .attr("id", "filter-" + windowIdAndTitle + "-variables-operation")
          .attr("href", "#")
          .attr("title", "Show all operation variables")
          .on("click", () => {
            
            let trial1ChangedVariablesFiltered = filterVariablesArray(functionDiffJson["trial1_variables_that_changed"], true);
            let trial2AddedVariablesFiltered = filterVariablesArray(functionDiffJson["trial2_variables_added"], true);
            let trial1RemovedVariablesFiltered = filterVariablesArray(functionDiffJson["trial1_variables_removed"], true);

            spanProperty.html("");
            writeHTMLDiffVariables(spanProperty, trial1ChangedVariablesFiltered, trial2AddedVariablesFiltered, trial1RemovedVariablesFiltered);

          })
          .append("i")
          .classed("fa fa-plus-square", true).append("span").style("margin-right","10px").text("Show all operation variables");;

          buttonDiv.append("span")
          .classed("toollink", true)
          .attr("id", "filter-" + windowIdAndTitle + "-variables-all")
          .attr("href", "#")
          .attr("title", "Show all variables")
          .on("click", () => {
            
            spanProperty.html("");
            writeHTMLDiffVariables(spanProperty, functionDiffJson["trial1_variables_that_changed"], functionDiffJson["trial2_variables_added"], functionDiffJson["trial1_variables_removed"]);

          })
          .append("i")
          .classed("fa fa-code", true).append("span").style("margin-right","10px").text("Show all variables");

          writeHTMLDiffVariables(spanProperty, functionDiffJson["trial1_variables_that_changed"], functionDiffJson["trial2_variables_added"], functionDiffJson["trial1_variables_removed"]);

        }else if(property == "arguments"){
          let symDifference = functionDiffJson[property+"_function_trial1"].filter((x: any) => !functionDiffJson[property+"_function_trial2"].includes(x))
                        .concat(functionDiffJson[property+"_function_trial2"].filter((x: any) => !functionDiffJson[property+"_function_trial1"].includes(x)));

          spanProperty.append("span").html(colorArrayElementsHTML(functionDiffJson[property+"_function_trial1"], symDifference, "red"));
          spanProperty.append("br");
          spanProperty.append("span").html(colorArrayElementsHTML(functionDiffJson[property+"_function_trial2"], symDifference, "green"));
        } else {
          spanProperty.append("span").style("color", "red").text(functionDiffJson[property+"_function_trial1"].toString());
          spanProperty.append("br");
          spanProperty.append("span").style("color", "green").text(functionDiffJson[property+"_function_trial2"].toString());
        }

      }

    });

    let fileAccessAddedTitle = functionDiffWindow.append("p").style("font-weight", "bold").text(functionDiffJson["file_accesses_added"].length + " file accesses added:");
    let spanFileAccessAdded = functionDiffWindow.append("span").attr("id", "diff-function-file-access-added-span-"+crypto.randomUUID());
    addHideShowButton(fileAccessAddedTitle, "hide-and-show-button-file-access-added", spanFileAccessAdded.attr("id"));
    writeFileAccess(functionDiffJson["file_accesses_added"], spanFileAccessAdded, "green");


    let fileAccessRemovedTitle = functionDiffWindow.append("p").style("font-weight", "bold").text(functionDiffJson["file_accesses_removed"].length + " file accesses removed:");
    let spanFileAccessRemoved = functionDiffWindow.append("span").attr("id", "diff-function-file-access-removed-span-"+crypto.randomUUID());
    addHideShowButton(fileAccessRemovedTitle, "hide-and-show-button-file-access-removed", spanFileAccessRemoved.attr("id"));
    writeFileAccess(functionDiffJson["file_accesses_removed"], spanFileAccessRemoved, "red");
    
    
    let fileAccessReplacedTitle = functionDiffWindow.append("p").style("font-weight", "bold").text(functionDiffJson["file_accesses_replaced"].length + " file accesses replaced:")
    let spanFileAccessReplaced = functionDiffWindow.append("span").attr("id", "diff-function-file-access-replaced-span-"+crypto.randomUUID());
    addHideShowButton(fileAccessReplacedTitle, "hide-and-show-button-file-access-replaced", spanFileAccessReplaced.attr("id"));
    
    functionDiffJson["file_accesses_replaced"].forEach((file:any)=>{
      spanFileAccessReplaced.append("span").text("Name: " + file.name);
      spanFileAccessReplaced.append("br");
      //spanFileAccessReplaced.append("span").style("color", color).text("Mode: " + file.mode);
      //spanFileAccessReplaced.append("br");
      //spanFileAccessReplaced.append("span").style("color", color).text(" Buffering: " + file.buffering);
      //spanFileAccessReplaced.append("br");
      spanFileAccessReplaced.append("span").text("Content hash before changed from ").append("span").style("color", "red").text(file.content_hash_before_first_trial).on("click", ()=>{
        downloadFileContent(file.content_hash_before_first_trial, file.name);
      });
      spanFileAccessReplaced.append("span").text(" to ").append("span").style("color", "green").text(file.content_hash_before_second_trial).on("click", ()=>{
        downloadFileContent(file.content_hash_before_second_trial, file.name);
      });
      spanFileAccessReplaced.append("br");
      spanFileAccessReplaced.append("span").text("Content hash after changed from ").append("span").style("color", "red").text(file.content_hash_after_first_trial).on("click", ()=>{
        downloadFileContent(file.content_hash_after_first_trial, file.name);
      });
      spanFileAccessReplaced.append("span").text(" to ").append("span").style("color", "green").text(file.content_hash_after_second_trial).on("click", ()=>{
        downloadFileContent(file.content_hash_after_second_trial, file.name);
      });
      spanFileAccessReplaced.append("br");
      spanFileAccessReplaced.append("span").text("Timestamp changed from ").append("span").style("color", "red").text(file.timestamp_first_trial);
      spanFileAccessReplaced.append("span").text(" to ").append("span").style("color", "green").text(file.timestamp_second_trial);
      spanFileAccessReplaced.append("br");
      spanFileAccessReplaced.append("span").text("Checkpoint changed from ").append("span").style("color", "red").text(file.checkpoint_first_trial);
      spanFileAccessReplaced.append("span").text(" to ").append("span").style("color", "green").text(file.checkpoint_second_trial);
      //spanFileAccessReplaced.append("span").style("color", color).text("Function: " + file.stack);
      spanFileAccessReplaced.append("br");
      spanFileAccessReplaced.append("br");
    });

  function downloadFileContent(fileHash: any, fileName : any) {
    var link = document.createElement("a");
    link.download = fileName;
    link.href = window.location.origin + "/downloadFile/"+fileHash;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    link.remove();
  }  

  /* function showFileContent(fileHash: any, fileName : any) {
    fetch("getFileContent/" + fileHash, {
      method: 'GET', // *GET, POST, PUT, DELETE, etc.
      headers: {
        'Content-Type': 'application/json'
      },
    }).then((response) => {
      response.json().then((json) => {

      if(fileName.length > 50) fileName = fileName.substring(40);

      let modal = d3_select(document.getElementById("main"))
      .append("div").classed("modal fade show", true)
      .attr("id", "fileContentModal")
      .attr("tabindex", "-1")
      .attr("role", "dialog")
      .attr("aria-labelledby", "fileContentModal")
      .style("display", "none")
      .attr("aria-hidden", "false")
      .style("display", "block");
      
      let modalDialog = modal.append("div").classed("modal-dialog", true).attr("role","document").style("overflow-y","initial").style("max-height", "85%");

      let modalContent = modalDialog.append("div").classed("modal-content", true);
      
      let modalHeader = modalContent.append("div").classed("modal-header", true);
      modalHeader.append("h5").classed("modal-title", true).attr("id", "fileContentModalLabel").text("File "+fileName+"'s content:");
      modalHeader.append("button").classed("close", true).attr("data-dismiss", "modal").attr("aria-label", "Close")
      .append("span").attr("aria-hidden", "true").html("&times;").on("click", () => modal.remove());

      let modalBody = modalContent.append("div").classed("modal-body", true).style("overflow-y", "auto").style("height", "80vh");
      modalBody.append("p").html(json.file_content.replace("\r\n", "<br>").replace("\n", "<br>"));
      });
    });
  } */
  }