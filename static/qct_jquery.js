function set_status(s) {
    $('#status').text(s);
}
 
tm=0;
 
dirty={};
 
save_endpoint='/pycwb/saveAttributes';

function resetTimeout() {
  if (tm!=0) {
    window.clearTimeout(tm);
  }
  set_status("modified"+JSON.stringify(dirty));
  tm=window.setTimeout("after_timeout()",600);
}

function after_save(data,textStatus,req) {
  set_status("saved.");
  dirty={};
}

function after_error(req,status) {
    set_status('Error...'+req.responseText);
}
 
function after_timeout() {
    set_status("saving..."+JSON.stringify(dirty));
    ajaxRequest=new $.ajax({'type':'POST',
			    'url':save_endpoint,
			    'processData':false,
			    'data':JSON.stringify(dirty),
			    'contentType':'text/json',
			    'success':after_save,
			    'error':after_error});
    tm=0;
}

function after_blur(field_id) {
  dirty[field_id]=$('#'+field_id).value;
  set_status("(changed)");
  resetTimeout();
}
 
var what_chosen={};
function chosen(item,what) {
if (what_chosen[item]) {
  $('#'+item+"_"+what_chosen[item]).className='choose';
}
$('#'+item+"_"+what).className='chosen';
what_chosen[item]=what;
dirty[item]=what;
resetTimeout();
}