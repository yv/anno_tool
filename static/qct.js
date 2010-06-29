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

function after_blur_2(field_id) {
    if (what_chosen[field_id]) {
	var item=document.getElementById(field_id+"_"+what_chosen[item]);
	if (item) { item.className='choose'; }
    }
    val=$('txt:'+field_id).value;
    var item2=document.getElementById(field_id+"_"+val);
    if (item2) { item2.className='chosen'; }
    chosen[field_id]=val;
    dirty[field_id]=val;
    set_status("(changed)");
    resetTimeout();
}

function chosen_txt(field_id,val) {
    if (what_chosen[field_id]) {
	var item=document.getElementById(field_id+":"+what_chosen[item]);
	if (item) { item.className='choose'; }
    }
    $('txt:'+field_id).value=val;
    var item2=document.getElementById(field_id+"_"+val);
    if (item2) { item2.className='chosen'; }
    chosen[field_id]=val;
    dirty[field_id]=val;
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