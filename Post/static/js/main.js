"use strict"
/*
# error-reporting-tool - view definitions
#
# Copyright (C) 2015 Intel Corporation
#
# Licensed under the MIT license, see COPYING.MIT for details
*/

/* from libtoaster.js
 * parses the query string of the current window.location to an object */
function parseUrlParams() {
  var string = window.location.search
  string = string.substr(1);
  var stringArray = string.split ("&");
  var obj = {};

  for (var i in stringArray) {
    var keyVal = stringArray[i].split ("=");
    obj[keyVal[0]] = keyVal[1];
  }

  return obj;
};

/* from libtoaster.js
 * takes a flat object and outputs it as a query string
 * e.g. the output of dumpsUrlParams
 */
function dumpsUrlParams(obj) {
  var str = "?";

  for (var key in obj){
    if (!obj[key])
      continue;

    str += key+ "="+obj[key].toString();
    str += "&";
  }

  /* return and remove trailing & */
  return str.substr(0,str.length-1);
};

$(document).ready(function(){

  /* Use json encoding for cookie content */
  $.cookie.json = true;

  $(".pagesize").change(function(){
    var search = parseUrlParams();
    search.limit = this.value;

    window.location.search = dumpsUrlParams(search);
  });

  $(".pagination a").each(function() {
    if ($(this).parent().hasClass("disabled")) {
      return
    }

    var search = parseUrlParams();
    search.page = $(this).data('page');

    $(this).attr("href", dumpsUrlParams(search));
  });

  $(".sort-col").click(function(){
    var search = parseUrlParams();
    search.order_by = $(this).data("order-by");
    if (search.order_by)
      window.location.search = dumpsUrlParams(search);
  });

  $("#clear-filter-btn").click(function(){
    var search = parseUrlParams();
    delete search.filter;
    delete search.type;

    window.location.search = dumpsUrlParams(search);
  });

  $(".filter").click(function(e){
    var search = parseUrlParams();
    search.filter = $(this).data('filter');
    search.type = $(this).data('type');

    window.location.search = dumpsUrlParams(search);
  });

  /* Toggle a column */
  $(".col-toggle").change(function(){

    if ($(this).prop("checked")){
      console.log("."+$(this).val());
      $("."+$(this).val()).show();
    } else {
      $("."+$(this).val()).hide();
    }

    var disabled_cols = [];
    /* Update the cookie */
    $("th").not(":visible").map(function(){
      disabled_cols.push($(this).prop("class"));
    });

    $.cookie("cols", disabled_cols);
  });

  /* Display or hide table columns before showing the table */
  var cols_hidden = $.cookie("cols");
  if (cols_hidden) {
    console.log("doing cookie func");
    console.log ("cols_hidden:");
    console.log (cols_hidden);
    $("#errors-table th").each(function(){
      var clclass = $(this).prop("class");

      for (var i in cols_hidden){
        if (cols_hidden[i] == clclass){
          $("."+clclass).hide();
          $("#checkbox-"+clclass).removeAttr("checked");
        }
      }
    });
  }
  $("#errors-table").show();

  $('.commit > div').popover({
      placement:'left',
      html: true
  });

  $(".recipe_version a").tooltip();

  $(".back-btn").click(function (e){
    window.history.back();
    e.preventDefault();
  });

  /* show filter icon only on hover. Use visibility to make sure we have 
   * space allocated to the icon/link.
   */
  $("td").hover(function () {
    $(this).children(".filter").css('visibility','visible');

  });
  $("td").mouseleave(function () {
    $(this).children(".filter").css('visibility','hidden');
  });

  $("th").hover(function () {
    $(this).children(".sorting-arrows").css('visibility','visible');

  });

  $("th").mouseleave(function () {
    $(this).children(".sorting-arrows").css('visibility','hidden');
  });


  $('.chbxtoggle').each(function () {
    //     showhideTableColumn($(this).attr('id'), $(this).is(':checked'))
  });
  //turn edit columns dropdown into a multi-select menu$
  $('.dropdown-menu input, .dropdown-menu label').click(function(e) {
    e.stopPropagation();
  });$
  $(".icon-filter").tooltip({ container: 'body', html: true });
  // initialise the remove filter tooltips
  $("th .btn-mini").tooltip({ container: 'body', html: true, title:'Clear filter' });

});
