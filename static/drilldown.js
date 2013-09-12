if(!String.prototype.startsWith){
    String.prototype.startsWith = function (str) {
        return !this.indexOf(str);
    }
}

TP_VAL=3;
FP_VAL=2;
FN_VAL=1;
function CounterBin() {
    this.values=[0.0,0.0,0.0,0.0];
}
CounterBin.prototype.addVals=function(a,b) {
    this.values[a+b*2]+=1;
};
CounterBin.prototype.count=function(x) {
    this.values[x]+=1;
}
    CounterBin.prototype.computed_stats=['Prec','Recl','F1'];
CounterBin.prototype.basic_header=['Counts[pos]'];
CounterBin.prototype.compute_stats=function(){
    var vals=this.values;
    if (vals[3]==0) {
	return [0,0,0];
    }
    prec=vals[3]/(vals[3]+vals[2]);
    recl=vals[3]/(vals[3]+vals[1]);
    return [prec,recl,2*prec*recl/(prec+recl)];
};
CounterBin.prototype.basic_stats=function(){
    var vals=this.values;
    return [vals[1]+vals[3]];
};


function count_common(lblG,lblS) {
    var common=0;
    for (var i=0;i<lblG.length;i++) {
	var kG=lblG[i];
	for (var j=0;j<lblS.length;j++) {
	    var kS=lblS[j];
	    if (kS.startsWith(kG)) {
		common++;
	    }
	}
    }
    return common;
}

function CounterMLab() {
    this.dice=0;
    this.eq=0;
    this.count=0;
}
CounterMLab.prototype.addVals=function(a,b) {
    cc=count_common(a,b);
    if (cc==a.length && cc==b.length)  this.eq++;
    this.dice += 2.0*cc/(a.length+b.length);
    this.count++;
};

CounterMLab.prototype.computed_stats=['Dice','Equal'];
CounterMLab.prototype.basic_header=['Count'];
CounterMLab.prototype.compute_stats=function(){
    return [this.dice/this.count,this.eq/this.count];
};
CounterMLab.prototype.basic_stats=function(){
    return [this.count];
};
CounterMLab.prototype.toString=function(){
    return "CounterMLab(count="+this.count+"eq="+this.eq+")";
}


function isEmpty(o){
    for(var k in o){
	if(o.hasOwnProperty(k)) return false;
    }
    return true;
}


function RESplitter(val) {
    my_re=new RegExp(val);
    return function(row) {
	var i;
	var feats=row[1];
	var result=[];
	for (i=0;i<feats.length;i++) {
	    if (my_re.test(feats[i])) {
		result.push(feats[i]);
	    }
	}
	if (result.length==0) {
	    result.push(null);
	}
	return result;
    }
}

function make_split(splitter,counter,predictions) {
    var i,j;
    results={};
    for (i=0;i<data.length;i++) {
	var d=data[i];
	keys=splitter(d);
	for (j=0;j<keys.length;j++) {
	    var f=keys[j];
	    if (results[f]==undefined) {
            var cs=[];
            for (var k=0; k<columns.length; k++) {
                cs.push(counter());
            }
            results[f]=cs;
	    }
	    for (var k=0; k<columns.length; k++) {
            results[f][k].addVals(d[2],predictions[k][i]);
	    }
	}
    }
    return results;
}

display_filter={};
display_key=null;

function rels_binary(a,b) {
    if (a&&b) {
	val=TP_VAL;
    } else if (a) {
	val=FN_VAL;
    } else if (b) {
	val=FP_VAL;
    } else {
	return {};
    }
    return {'DC':val};
}

function rels_mlab(lblG,lblS) {
    var retval={};
    var seenS={};
    for (var i=0;i<lblG.length;i++) {
	var kG=lblG[i];
	var seenG=false;
	for (var j=0;j<lblS.length;j++) {
	    var kS=lblS[j];
	    if (kS.startsWith(kG)) {
		retval[kG]=TP_VAL;
		seenG=true;
		seenS[kS]=true;
		break;
	    }
	}
	if (!seenG) {
	    retval[kG]=FN_VAL;
	}
    }
    for (var j=0;j<lblS.length;j++) {
	var kS=lblS[j];
	if (!seenS[kS]) {
	    retval[kS]=FP_VAL;
	}
    }
    return retval;
}

function make_rel_table(counters) {
    var segments=['<table class="confusion">',
		  '<tr><th>relation</th><th>Prec</th><th>Recl</th><th>F1</th>'];
    for (k=1; k<columns.length; k++) {
	segments.push('<th>&Delta;TP</th><th>&Delta;FP</th><th>&Delta;F1</th>');
    }
    segments.push('</tr>');
    for (rel in counters) {
	var counter0=counters[rel][0];
	var count=counter0.basic_stats()[0];
	var vals=counter0.compute_stats();
	segments.push('<tr><th align="left">');
	segments.push(rel+' ('+count);
	segments.push(')</th><td><a href="javascript:set_filter(\''+rel+'\',2)">');
	segments.push(render_float(vals[0]));
	segments.push('</a></td><td><a href="javascript:set_filter(\''+rel+'\',1)">');
	segments.push(render_float(vals[1]));
	segments.push('</a></td><td><a href="javascript:set_filter(\''+rel+'\',3)">');
	segments.push(render_float(vals[2]));
	segments.push('</a></td>');
	for (k=1; k<columns.length; k++) {
	    var counterK=counters[rel][k];
	    var vals2=counterK.compute_stats();
	    segments.push('<td>');
	    segments.push(render_int(counterK.values[TP_VAL]-counter0.values[TP_VAL]));
	    segments.push('</td><td>');
	    segments.push(render_int(counterK.values[FP_VAL]-counter0.values[FP_VAL]));
	    segments.push('</td><td>');
	    segments.push(render_float(vals2[2]-vals[2]));
	    segments.push('</td>');
	}
	segments.push('</tr>');
    }
    segments.push('</table>');
    return segments.join('');
}


function set_filter(key,val) {
    if (display_filter[key]==val) {
	delete display_filter[key];
    } else {
	display_filter={};
	display_filter[key]=val;
    }
    drilldown(display_key);
}

function handle_popup(idx,fno) {
    var d=data[idx][1];
    alert(d[fno]);
}

function create_feature_links(idx,lst_out)
{
    var d=data[idx][1];
    for (var i=0; i<d.length; i++) {
	lst_out.push('<span class="feature" id="');
	lst_out.push('d'+idx+'f'+i+'" onclick="handle_popup('+idx+','+i+')">');
	lst_out.push(d[i]);
	lst_out.push('</span> ');
    }
}

function filter_wanted(rels,filt) {
    for (k in filt) {
	if (rels[k]==undefined ||
	    rels[k]!=filt[k]) {
	    return false;
	}
    }
    return true;
}

function drilldown(key) {
    var p=[];
    for (var i=0; i<columns.length; i++) {
	p.push(predictions[columns[i]]);
    }
    var counters={};
    wanted=[];
    if (key=='null') {key=null;}
    display_key=key;
    for (i=0;i<data.length;i++) {
	var d=data[i];
	var feats=d[1];
	var want=false;
	var rels0;
	for (j=0;j<feats.length;j++) {
	    if (feats[j]==key) {
		want=true;
		for (var k=0;k<columns.length;k++) {
		    var rels=relsFn(d[2],p[k][i]);
		    if (k==0) rels0=rels;
		    for (var rel in rels) {
			if (counters[rel]==undefined) {
			    relcount=[];
			    for (var m=0; m<columns.length; m++) {
				relcount.push(new CounterBin());
			    }
			    counters[rel]=relcount;
			}
			counters[rel][k].count(rels[rel]);
		    }
		}
		break;
	    }
	}
	if (want && 
	    (isEmpty(display_filter) || filter_wanted(rels0,display_filter))) {
	    wanted.push('<div class="example">');
	    wanted.push(snippets[i]);
	    wanted.push('<br>Gold:'+d[2]+' Sys:'+p[0][i]+'<br>');
	    create_feature_links(i,wanted);
	    wanted.push('</div>');
	}
    }
    $('#display').html('<h2>'+key+'</h2>'+make_rel_table(counters)+wanted.join(''));
}

function render_float(f) {
    return f.toFixed(3);
}

function render_int(f) {
    return f.toFixed(0);
}

function make_fixed_renderfn(col_no) {
    return function(aObj) {
	return aObj.aData[col_no].toFixed(3);
    }
}

function make_delta_renderfn(col_anchor, col_compare) {
    return function(aObj) {
	return (aObj.aData[col_compare]-aObj.aData[col_anchor]).toFixed(3);
    }
}

function make_table(split_data,basic_header,header, min_freq) {
    $('#display').html('<table class="display" id="results_table"></table>');
    all_results=[];
    all_columns=[{'sTitle':'key','sWidth':'7cm',
		  fnRender:function(aObj) {
		var d=aObj.aData[0];
		return '<a href="javascript:drilldown(\''+d.replace(/\"/g,'\\x22')+'\')">'+d+'</a>';
	    }
	},{'sTitle':'Count[pos]','sWidth':'2cm'}];
    var offset0=basic_header.length+1;
    for (var i=0;i<header.length;i++) {
	var renderfn=make_fixed_renderfn(i+basic_header.length+1);
	all_columns.push({'sTitle':header[i],
		    'fnRender':renderfn,
		    'sWidth':'2cm'});
    }
    for (var k=1;k<columns.length;k++) {
        var offset1=offset0+k*header.length;
        for (var i=0;i<header.length;i++) {
            var renderfn=make_delta_renderfn(i+offset0,i+offset1);
            all_columns.push({'sTitle':"&Delta;"+header[i],
                        'fnRender':renderfn,
                        'sWidth':'2cm'});
        }
    }
    for (var key in split_data) {
        var x=[key];
        if (split_data[key][0].count<min_freq) {
            continue;
        }
        x=x.concat(split_data[key][0].basic_stats()).concat(split_data[key][0].compute_stats());
        for (var k=1;k<columns.length;k++) {
            x=x.concat(split_data[key][k].compute_stats());
        }
        all_results.push(x);
    }
    $('#results_table').dataTable({
	    'aaData':all_results,
		'aoColumns':all_columns,
		'sPaginationType':'full_numbers'
		});
}

function do_setup(type) {
    if (type=='binary') {
	counterFactory=function(){return new CounterBin();};
	relsFn=rels_binary;
    } else if (type=='mlab') {
	counterFactory=function(){return new CounterMLab();};
	relsFn=rels_mlab;
    }
}

function reset_display() {
    display_filter={};
    feat_prefix=$('#feat_re').val();
    min_freq=0+$('#minfreq').val();
    var obj=counterFactory();
    basic_header=obj.basic_header;
    header=obj.computed_stats;
    var ps=[];
    for (var i=0; i<columns.length; i++) {
	ps.push(predictions[columns[i]]);
    }
    if (feat_prefix) {
	split_data=make_split(RESplitter('^'+feat_prefix),
			      counterFactory,
			      ps);
	make_table(split_data,basic_header,header,min_freq);
    } else {
	split_data=make_split(function() {return [null];},
			      counterFactory,
			      ps);
	make_table(split_data,basic_header,header,min_freq);
    }
}


//
// agreement-related functions
//

function make_agr_table(counters) {
    var segments=['<table class="confusion">',
		  '<tr><th>relation</th><th>F1</th>'];
    segments.push('</tr>');
    for (rel in counters) {
	var counter0=counters[rel][0];
	var count=counter0.basic_stats()[0];
	var vals=counter0.compute_stats();
	segments.push('<tr><th align="left"><a href="javascript:show_by_rel(');
	segments.push("'"+rel+"')\">")
	segments.push(rel+'</a> ('+count);
	segments.push(')</th><td>');
	segments.push(render_float(vals[2]));
	segments.push('</td>');
	segments.push('</tr>');
    }
    segments.push('</table>');
    return segments.join('');
}

function shorten_rels(all_rels,depth) {
  var retval=[];
  for (var i=0;i<all_rels.length; i++) {
    var lbl=all_rels[i];
    var lbl_new=[];
    for (var j=0;j<lbl.length;j++) {
      lbl_new.push(lbl[j].split('.').slice(0,depth).join('.'));
    }
    retval.push(lbl_new);
  }
  return retval;
}

function agreement_refresh()
{
  anno1_idx=$('#anno1_chooser').selectmenu('value');
  anno2_idx=$('#anno2_chooser').selectmenu('value');
  taxo_depth=1+$('#taxo_depth').selectmenu('value');
  pred1=shorten_rels(predictions[anno1_idx],taxo_depth);
  pred2=shorten_rels(predictions[anno2_idx],taxo_depth);
  //alert('anno1:'+anno1_idx+' anno2:'+anno2_idx+' depth:'+taxo_depth);
  var counter=new CounterMLab();
  var rel_counters={}
  for (var i=0;i<pred1.length;i++) {
    counter.addVals(pred1[i],pred2[i]);
    rels=rels_mlab(pred1[i],pred2[i]);
    for (var rel in rels) {
     if (rel_counters[rel]==undefined) {
       rel_counters[rel]=[new CounterBin()];
     }
     rel_counters[rel][0].count(rels[rel]);
    }
  }
  stats=counter.compute_stats();
  $('#display').html('dice: '+render_float(stats[0])+' eq: '+render_float(stats[1])+make_agr_table(rel_counters));
  $('#examples').html('');
}

function contains_rel(lbl,rel)
{
  for (var i=0;i<lbl.length;i++)
  {
    if (lbl[i]==rel) return true;
  }
  return false;
}

function show_by_rel(rel)
{
  anno1_idx=$('#anno1_chooser').selectmenu('value');
  anno2_idx=$('#anno2_chooser').selectmenu('value');
  display_snippets=[];
  for (var i=0;i<pred1.length;i++) {
    var wanted=(contains_rel(pred1[i],rel)||contains_rel(pred2[i],rel));
    if (wanted) {
      display_snippets.push(snippets[i]);
      display_snippets.push('<table>');
      display_snippets.push('<tr><td><b>'+columns[anno1_idx]+'</b>:</td><td>'+pred1[i].join(', ')+'</td></tr>');
      display_snippets.push('<tr><td><b>'+columns[anno2_idx]+'</b>:</td><td>'+pred2[i].join(', ')+'</td></tr>');
      display_snippets.push('</table>');
    }
  }
  $('#examples').html(display_snippets.join(''));
}
