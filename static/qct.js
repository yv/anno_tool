function set_status(s) {
  $('status').innerHTML=s;
}
 
tm=0;
 
dirty={};
 
function resetTimeout() {
  if (tm!=0) {
    window.clearTimeout(tm);
  }
  tm=window.setTimeout("after_timeout()",600);
}

function after_save() {
  set_status("saved.");
  dirty={};
}

function after_error() {
    set_status('Error: '+ajaxRequest.responseText);
}
 
function after_timeout() {
    ajaxRequest=new Ajax.Request('/pycwb/saveAttributes',{
				     method: 'post',
				     contentType: 'text/json',
				     postBody: JSON.stringify(dirty),
				     onSuccess: after_save,
				     onFailure: after_error});
    set_status("saving...");
    tm=0;
}
 
function after_blur(field_id) {
  dirty[field_id]=$(field_id).value;
  set_status("(changed)");
  resetTimeout();
}
 
var what_chosen={};
function chosen(item,what) {
if (what_chosen[item]) {
  document.getElementById(item+"_"+what_chosen[item]).className='choose';
}
document.getElementById(item+"_"+what).className='chosen';
what_chosen[item]=what;
dirty[item]=what;
resetTimeout();
}