// tokens=['Dies','ist','ein','Beispiel','.',
//	'Es','besteht','aus','mehreren','Sätzen',',',
//	'die','in','Diskurssegmente','eingeteilt','werden','.'];

//sentences=[0,5];
//edus=[0,5,11];
//indent=[0,0,0];
//topics=[];

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
		s+='</div>';
		in_div=false;
	    }
	    s+='<div class="topic" id="t'+next_topic+
		'" onclick="set_curword('+i+');edit_topic();"><span class="edu-label">T'+
		next_topic+'</span>'+
		topics[next_topic][1]+'</div>';
	    next_topic++;
	}
	if (edus[next_edu]==i) {
	    if (in_div) {
		s+='</div>';
	    }
	    next_edu++;
	    sub_edu++;
	    if (sentences[next_sent]==i) {
		sub_edu=0;
		next_sent++;
	    }
	    s+='<div class="edu" id="edu'+next_edu+
		'" style="margin-left:'+(indent[next_edu-1]*INDENT_STEP)+'px"><span class="edu-label">'+
		next_sent+'.'+sub_edu+'</span>';
	    in_div=true;
	}
	s+='<span class="word" id="w'+i+'">'+tokens[i]+'</span> ';
    }
    if (in_div) {
	s +='</div>';
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
    } else if (key == 16 || key == 17) {
	// ignore shift, ctrl
    } else if (key == 84) {
	edit_topic();
	return false;
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
    } else if (key==13 || key==27 ||
	       key==40 || key==38) {
	$('#t'+cur_topic).html('<span class="edu-label">T'+
			       cur_topic+'</span>'+
			       topics[cur_topic][1]);
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

function fill_segments() {
    redisplay_all();
    $('#fake-input').focus();
}

