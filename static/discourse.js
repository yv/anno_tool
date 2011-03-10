// tokens=['Dies','ist','ein','Beispiel','.',
//	'Es','besteht','aus','mehreren','Sätzen',',',
//	'die','in','Diskurssegmente','eingeteilt','werden','.'];

//sentences=[0,5];
//edus=[0,5,11];
//indent=[0,0,0];
//topics=[];
//nonedu={}

topic_rels={};

cur_word=0;

INDENT_STEP=20;

function make_segments() {
    var in_div=false;
    var next_sent=0;
    var next_edu=0;
    var next_topic=0;
    var sub_edu;
    var s='';
    for (var i=0; i<tokens.length;i++) {
	if (next_topic<topics.length &&
	    topics[next_topic][0]==i) {
	    if (in_div) {
		s+='<span class="edu-rel">'+rel+'</span></div>';
		in_div=false;
	    }
	    var rel=topic_rels['T'+next_topic];
	    if (rel==undefined) { rel='(no rel)'; }
	    s+='<div class="topic" id="t'+next_topic+
		'" onclick="set_curword('+i+');edit_topic();"><span class="edu-label">T'+
		next_topic+'</span>'+
		topics[next_topic][1]+'<span class="edu-rel">'+rel+'</span></div>';
	    next_topic++;
	}
	if (edus[next_edu]==i) {
	    if (in_div) {
		s+='<span class="edu-rel">'+rel+'</span></div>';
	    }
	    next_edu++;
	    sub_edu++;
	    if (sentences[next_sent]==i) {
		sub_edu=0;
		next_sent++;
	    }
	    if (nonedu[i]) {
		cls='nonedu';
	    } else if (uedus[i]) {
		cls='uedu';
	    } else {
		cls='edu';
	    }
	    rel=topic_rels[''+next_sent+'.'+sub_edu];
	    if (rel==undefined) { rel='(no rel)'; }
	    s+='<div class="'+cls+'" id="edu'+next_edu+
		'" style="margin-left:'+(indent[next_edu-1]*INDENT_STEP)+'px"><span class="edu-label">'+
		next_sent+'.'+sub_edu+'</span>';
	    in_div=true;
	}
	s+='<span class="word" id="w'+i+'">'+tokens[i]+'</span> ';
    }
    if (in_div) {
	s +='<span class="edu-rel">'+rel+'</span></div>';
    } else {
	s+='(empty)';
    }
    return s;
}

function find_current_sentence() {
    for (i=0;i<sentences.length;i++) {
	if (sentences[i]>cur_word) {
	    return i-1;
	}
    }
    return sentences.length-1;
}

function find_current_edu() {
    for (i=0;i<edus.length;i++) {
	if (edus[i]>cur_word) {
	    return i-1;
	}
    }
    return edus.length-1;
}

function dedent_edu() {
    var pos=find_current_edu();
    if (indent[pos]>0) {
	indent[pos]-=1;
	$('#edu'+(pos+1)).css('margin-left',(indent[pos]*INDENT_STEP)+'px');
    }
    dirty['indent']=indent;
    resetTimeout();
}

function indent_edu() {
    var pos=find_current_edu();
    indent[pos]+=1;
    $('#edu'+(pos+1)).css('margin-left',(indent[pos]*INDENT_STEP)+'px');
    dirty['indent']=indent;
    resetTimeout();
}

function addSplit(pos) {
    for (var i=0;i<edus.length;i++) {
	if (edus[i]==pos) return false;
	if (edus[i]>pos) {
	    edus.splice(i,0,pos);
	    indent.splice(i,0,i>0?indent[i-1]:0);
	    dirty['edus']=edus;
	    dirty['indent']=indent;
	    resetTimeout();
	    return true;
	}
    }
    edus.push(pos);
    if (indent.length>0) {
	my_indent=indent[indent.length-1];
    } else {
	my_indent=0;
    }
    indent.push(my_indent);
    dirty['edus']=edus;
    dirty['indent']=indent;
    resetTimeout();
    return true;
}

function delSplit(pos) {
    for (var i=0;i<sentences.length;i++) {
	if (sentences[i]==pos) {
	    return false;
	}
    }
    for (var i=0;i<edus.length;i++) {
	if (edus[i]==pos) {
	    edus.splice(i,1);
	    indent.splice(i,1);
	    dirty['edus']=edus;
	    dirty['indent']=indent;
	    resetTimeout();
	    return true;
	}
    }
    return false;
}

function redisplay_all() {
    var top=$('#text').attr('scrollTop');
    html_content=make_segments();
    $('#text').html(html_content+'<input id="fake-input">');
    $('#w'+cur_word).addClass('active');
    $('#fake-input').focus().css('visibility','hidden').
	keydown(text_keydown);
    $('.word').click(focus_text);
    $('#text').attr('scrollTop',top);
}

function set_curword(n) {
    cur_word=n;
    $('.active').removeClass('active');
    var w=$('#w'+cur_word);
    var t=$('#text');
    w.addClass('active');
    var top=t.attr('scrollTop');
    var offset=w.position();
    var height=t.innerHeight();
    var w_height=w.outerHeight();
    if (offset.top<0) {
	t.attr('scrollTop',top+offset.top-4);
    } else {
	var pos2=offset.top+w_height;
	if (pos2>height) {
	    t.attr('scrollTop',top+pos2-height+4);
	}
    }
}

function text_keydown(event) {
    var key=event.keyCode || 0;
    if (key==39) {
	// right
	if (event.shiftKey) {
	    indent_edu();
	} else if (cur_word<tokens.length) {
	    set_curword(cur_word+1);
	}
    } else if (key == 37) {
	// left
	if (event.shiftKey) {
	    dedent_edu();
	} else if (cur_word>0) {
	    set_curword(cur_word-1);
	}
    } else if (key == 38) {
	// up
	pos=find_current_edu();
	cur_word=edus[pos];
	for (var i=0;i<topics.length;i++) {
	    if (topics[i][0]==cur_word) {
		edit_topic();
		return false;
	    }
	}
	if (pos>0) {
	    set_curword(edus[pos-1]);
	}
    } else if (key == 40) {
	// down
	pos=find_current_edu();
	if (pos<edus.length-1) {
	    set_curword(edus[pos+1]);
	    for (var i=0;i<topics.length;i++) {
		if (topics[i][0]==cur_word) {
		    edit_topic();
		    break;
		}
	    }
	}
    } else if (key == 13) {
	// enter -> split DS
	var result=addSplit(cur_word);
	if (!result) {
	    $('#status').text("geht nicht.");
	} else {
	    redisplay_all();
	}
    } else if (key == 8) {
	var result=delSplit(cur_word);
	if (!result) {
	    $('#status').text("geht nicht.");
	} else {
	    redisplay_all();
	}
    } else if (key == 16 || key == 17 || key == 0) {
	// ignore shift, ctrl, mod4
    } else if (key == 84) {
	edit_topic();
	return false;
    } else if (key == 78) {
	// N - toggle non-edu status
	var pos=edus[find_current_edu()];
	if (nonedu[pos]) {
	    delete nonedu[pos];
	} else {
	    nonedu[pos]=1;
	}
	dirty['nonedu']=nonedu;
	resetTimeout();
	redisplay_all();
    } else if (key == 219) {
	var pos=edus[find_current_edu()];
	if (uedus[pos]) {
	    delete uedus[pos];
	} else {
	    uedus[pos]=1;
	}
	dirty['uedus']=uedus;
	resetTimeout();
	redisplay_all();	
    } else if (key == 119) {
	// F8 - show text info
	$info.html("<a href=\"javascript:window.open('/pycwb/sentence/"+(sent_id+1+find_current_sentence())+
		   "');\">sentence id:"+(sent_id+1+find_current_sentence())+"</a>")
	    .dialog('open');
    } else if (key == 118) {
	$rels.dialog('open');
	//$('#status').text('open rels:'+$rels);
    } else {
	alert("bla"+event.keyCode);
    }
    return false;
}

function edit_topic() {
    cur_off=sentences[find_current_sentence()];
    cur_word=cur_off;
    cur_topic=-1;
    for (var i=0;i<topics.length;i++) {
	if (topics[i][0]==cur_off) {
	    cur_topic=i;
	    break;
	} else if (topics[i][0]>cur_off) {
	    topics.splice(i,0,[cur_off,'']);
	    cur_topic=i;
	    break;
	}
    }
    if (cur_topic==-1) {
	cur_topic=topics.length;
	topics.push([cur_off,'']);
    }
    redisplay_all();
    $('#t'+cur_topic).html('<span class="edu-label">T'+
			       cur_topic+'</span>'+
			   '<input id="topic_ct" width="80"></span>');
    //$('#auxinput').html('<input id="topic_ct" width="80">');
    $('#topic_ct').attr('value',topics[cur_topic][1]).
	keydown(topic_keydown).
	keyup(topic_changed).focus();
    $('.active').removeClass('active');
}

function topic_keydown(event) {
   var key=event.keyCode || 0;
    var val=$('#topic_ct').attr('value');
    if (key==27 && val=='' ||
	key==8 && val=='') {
	topics.splice(cur_topic,1);
	redisplay_all();
	event.preventDefault();
    } else if (key==13 || key==27 ||
	       key==40 || key==38) {
	var rel=topic_rels['T'+cur_topic];
	if (rel==undefined) { rel='(no rel)'; }
	$('#t'+cur_topic).html('<span class="edu-label">T'+
			       cur_topic+'</span>'+
			       topics[cur_topic][1]+'<span class="edu-rel">'+rel+'</span>');
	refocus_text();
	if (key==38) {
	    var sent=find_current_edu();
	    if (sent>0) {
		cur_word=edus[sent-1];
	    }
	}
	set_curword(cur_word);
    }
}

function topic_changed(event) {
    var val=$('#topic_ct').attr('value');
    var key=event.keyCode || 0;
    if (val!=topics[cur_topic][1]) {
	topics[cur_topic][1]=val;
	dirty['topics']=topics;
	resetTimeout();
    }
}

function refocus_text() {
    var top=$('#text').attr('scrollTop');
    $('#fake-input').css('visibility','visible').focus();
    $('#fake-input').css('visibility','hidden');
    $('#text').attr('scrollTop',top);
}

function focus_text(event) {
    var where=$(this);
    refocus_text();
    if (where) {
	if (where.attr('id')[0]=='w') {
	    var newpos=parseInt(where.attr('id').substr(1));
	    set_curword(newpos);
	} else {
	    alert(where.attr('id'));
	}
    }
}

var edu_re="[0-9]+(?:\\.[0-9]+)?";
var topic_re="T[0-9]+";
var span_re="(?:"+edu_re+"(?:-"+edu_re+")?|"+topic_re+")";
//var span_re=edu_re;
var relation_re=new RegExp("(\\w+(?:[- ]\\w+)*|\\?)\\s*\\(\\s*("+span_re+")\\s*,\\s*("+span_re+")\\s*\\)\\s*");
//var relation_re=new RegExp("(\\w+)\\((\\w+),(\\w+)\\)");
var comment_re=new RegExp("//.*$");
function parse_relations(rels) {
    var errors='';
    topic_rels={};
    lines=rels.split(/[\r\n]+/);
    for (var i=0; i<lines.length; i++) {
	var line=lines[i];
	line.replace(comment_re,'');
	if (line.match(/^$/)) {
	    continue;
	}
	var result=line.match(relation_re);
	if (result==null) {
	    errors=errors+'cannot parse: '+line+'\n';
	} else {
	    var rel1=result[2];
	    if (rel1.match('T[0-9]+')) {
	    } else {
		rel1=rel1.split('-')[0];
		if (rel1.match('^[0-9]+$')) {
		    rel1=rel1+'.0';
		}
	    }
	    if (topic_rels[rel1]==undefined) {
		topic_rels[rel1]=line;
	    }  else if (topic_rels[rel1].match('^<br>')) {
		topic_rels[rel1]+='<br>'+line;
	    } else {
		topic_rels[rel1]='<br>'+topic_rels[rel1]+'<br>'+line;
	    }
	    //errors=errors+'Relation:'+result[1]+' arg1:'+result[2]+' arg2:'+result[3]+'\n';
	}
    }
    return errors;
}

function fill_segments() {
    var errors=parse_relations(relations);
    redisplay_all();
    if (errors=='') {
	$('#status').text("loaded.");
    } else {
	$('#status').html("relation errors:"+errors.replace('\n','<br>'));
    }	
    $('#fake-input').focus();
}

