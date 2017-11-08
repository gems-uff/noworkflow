define(function() { return /******/ (function(modules) { // webpackBootstrap
/******/ 	// The module cache
/******/ 	var installedModules = {};
/******/
/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {
/******/
/******/ 		// Check if module is in cache
/******/ 		if(installedModules[moduleId]) {
/******/ 			return installedModules[moduleId].exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = installedModules[moduleId] = {
/******/ 			i: moduleId,
/******/ 			l: false,
/******/ 			exports: {}
/******/ 		};
/******/
/******/ 		// Execute the module function
/******/ 		modules[moduleId].call(module.exports, module, module.exports, __webpack_require__);
/******/
/******/ 		// Flag the module as loaded
/******/ 		module.l = true;
/******/
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/
/******/
/******/ 	// expose the modules object (__webpack_modules__)
/******/ 	__webpack_require__.m = modules;
/******/
/******/ 	// expose the module cache
/******/ 	__webpack_require__.c = installedModules;
/******/
/******/ 	// define getter function for harmony exports
/******/ 	__webpack_require__.d = function(exports, name, getter) {
/******/ 		if(!__webpack_require__.o(exports, name)) {
/******/ 			Object.defineProperty(exports, name, {
/******/ 				configurable: false,
/******/ 				enumerable: true,
/******/ 				get: getter
/******/ 			});
/******/ 		}
/******/ 	};
/******/
/******/ 	// getDefaultExport function for compatibility with non-harmony modules
/******/ 	__webpack_require__.n = function(module) {
/******/ 		var getter = module && module.__esModule ?
/******/ 			function getDefault() { return module['default']; } :
/******/ 			function getModuleExports() { return module; };
/******/ 		__webpack_require__.d(getter, 'a', getter);
/******/ 		return getter;
/******/ 	};
/******/
/******/ 	// Object.prototype.hasOwnProperty.call
/******/ 	__webpack_require__.o = function(object, property) { return Object.prototype.hasOwnProperty.call(object, property); };
/******/
/******/ 	// __webpack_public_path__
/******/ 	__webpack_require__.p = "https://unpkg.com/noworkflow@0.0.7/lib/";
/******/
/******/ 	// Load entry module and return exports
/******/ 	return __webpack_require__(__webpack_require__.s = 0);
/******/ })
/************************************************************************/
/******/ ([
/* 0 */
/***/ (function(module, exports, __webpack_require__) {

"use strict";


Object.defineProperty(exports, "__esModule", {
  value: true
});

var _package = __webpack_require__(1);

Object.defineProperty(exports, 'version', {
  enumerable: true,
  get: function get() {
    return _package.version;
  }
});

/***/ }),
/* 1 */
/***/ (function(module, exports) {

module.exports = {"private":false,"name":"@noworkflow/nbextension","version":"0.0.7","description":"A Jupyter Notebook extension for noWorkflow","main":"lib/index.js","keywords":["jupyter"],"dependencies":{"@noworkflow/history":"0.0.9","@noworkflow/trial":"0.0.6","@noworkflow/utils":"0.0.7","d3":"^4.11.0","file-saver":"^1.3.3"},"devDependencies":{"babel-core":"^6.26.0","babel-loader":"^7.1.2","babel-preset-env":"^1.6.0","css-loader":"^0.28.7","file-loader":"^1.1.5","json-loader":"^0.5.7","style-loader":"^0.19.0","url-loader":"^0.6.2","watch":"^1.0.2","webpack":"^3.6.0"},"scripts":{"build":"webpack","watch":"watch \"npm run build\" src --wait 10 --ignoreDotFiles","prepublish":"npm run build","extension:install":"jupyter nbextension install --symlink --py --sys-prefix noworkflow","extension:uninstall":"jupyter nbextension uninstall --py --sys-prefix noworkflow","extension:enable":"jupyter nbextension enable --py --sys-prefix noworkflow","extension:disable":"jupyter nbextension disable --py --sys-prefix noworkflow","clean":"rimraf ../../../capture/noworkflow/jupyter"},"repository":{"type":"git","url":"https://github.com/gems-uff/noworkflow.git"},"author":"Joao Felipe Pimentel <joaofelipenp@gmail.com>","license":"MIT","bugs":{"url":"https://github.com/gems-uff/noworkflow/issues"},"homepage":"http://gems-uff.github.io/noworkflow"}

/***/ })
/******/ ])});;
//# sourceMappingURL=index.js.map