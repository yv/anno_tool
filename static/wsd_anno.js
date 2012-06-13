function toggle_sense(item,what) {
    var sense=example_hash[item];
    if (sense[what]) {
	sense[what]=0;
	$('#'+item+"_"+what).addClass('choose').removeClass('chosen');
    } else {
	sense[what]=1;
	$('#'+item+"_"+what).addClass('chosen').removeClass('choose');
    }
    dirty[item+'-sense']=sense;
    set_status("(changed)");
    resetTimeout();
}

function create_widgets() {
  var tmpl_example=_.template($('#wsd-widget').html());
  var parts=[];
  example_hash={};
  for (var i=0;i<examples.length; i++) {
      var ex=examples[i];
      parts.push(tmpl_example(ex));
      example_hash[ex._id]=ex.sense?ex.sense:{};
  }
  $('#panel').html(parts.join(''));
}