function toggle_sense(item,what) {
    var sense=example_hash[item].sense;
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

function has_entry(obj) {
    if (!obj) return false;
    for (key in obj) {
	if (obj.hasOwnProperty(key)) return true;
    }
    return false;
}

function create_widgets(hide_done) {
  var tmpl_example=_.template($('#wsd-widget').html());
  var parts=[];
  example_hash={};
  if (hide_done) {
      parts.push('<p><a onclick="create_widgets(false)">Show all</a></p>');
  } else {
      parts.push('<p><a onclick="create_widgets(true)">Hide completed</a></p>');
  }
  for (var i=0;i<examples.length; i++) {
      var ex=examples[i];
      if (!hide_done ||
	  !has_entry(ex.sense) || ex.comment) {
	  parts.push(tmpl_example(ex));
      }
      if (!ex.sense) ex.sense={};
      example_hash[ex._id]=ex;
  }
  $('#panel').html(parts.join(''));
}

function changed_comment(item) {
    var field_id=item+'-comment';
    var field_val=$('#'+field_id).val();
    example_hash[item].comment=field_val;
    dirty[field_id]=field_val;
    set_status("(changed)");
    resetTimeout();
}
