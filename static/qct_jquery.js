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
  set_status("modified");
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

function after_blur_2(field_id) {
    if (what_chosen[field_id]) {
	var item=$('#'+field_id+"_"+what_chosen[item]);
	if (item) { item.className='choose'; }
    }
    val=$('txt-'+field_id).value;
    var item2=$('#'+field_id+"_"+val);
    if (item2) { item2.className='chosen'; }
    chosen[field_id]=val;
    dirty[field_id]=val;
    set_status("(changed)");
    resetTimeout();
}
 
var what_chosen={};
function chosen(item,what) {
if (what_chosen[item]) {
    $('#'+item+"_"+what_chosen[item]).addClass('choose').removeClass('chosen');
}
$('#'+item+"_"+what).addClass('chosen').removeClass('choose');
what_chosen[item]=what;
dirty[item]=what;
resetTimeout();
}
