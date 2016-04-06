'use strict';

var ctfApp = angular.module('ctfApp', [
    'ngRoute',
    'ctfControllers'
]);

// routing
ctfApp.config(['$routeProvider',
  function($routeProvider) {
    $routeProvider.
      when('/services', {
        templateUrl: 'static/partials/services.html',
        controller: 'ServicesCtrl'
      }).
      when('/submit_flag', {
        templateUrl: 'static/partials/submit_flag.html',
        controller: 'FlagCtrl'
      }).
      when('/scoreboard', {
        templateUrl: 'static/partials/scoreboard.html',
        controller: 'ScoreboardCtrl'
      }).
      when('/welcome', {
        templateUrl: 'static/partials/welcome.html',
        controller: 'ConfigCtrl'
      }).
      when('/exploits_status', {
          templateUrl: 'static/partials/exploit_status.html',
          controller: 'ExploitLogsCtrl'
      }).
      when('/containers_to_update', {
          templateUrl: 'static/partials/containers_updated.html',
          controller: 'ContainersUpdatedCtrl'
      }).
      otherwise({
        redirectTo: '/welcome'
      });
  }]);

