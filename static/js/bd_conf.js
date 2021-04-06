"use strict";

function min(x,y){
    return x < y ? x : y ;
}

function abs(x){
    return x < 0 ? -x : x;
}

function clamp( lb, x, ub ){
    x = lb <= x ? x : lb;
    x = x <= ub ? x : ub;
    return x;
}

function int( x ){
    return x - (x % 1);
}

function get_rels(r,e){
    var pt = [];
    pt[0] = e.clientX - r.left;
    pt[1] = e.clientY - r.top;
    return pt;
}

function get_rect(pta,ptb){
    var left_rel = min(pta[0], ptb[0]);
    var top_rel = min(pta[1], ptb[1]);
    var w = abs(pta[0]-ptb[0]);
    var h = abs(pta[1]-ptb[1]);
    return [ left_rel, top_rel, w, h ];
}

function loadDoc(href, target) {
    var xhttp = new XMLHttpRequest();
    /* Closure */
    xhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            target.src = this.responseText;
        }
    };
    xhttp.open("GET", href, true);
    xhttp.send();
}

function update_all_rects(){
    for (var i = 0; i < records.length; i++){
        update_rects(i);
    }
}

function update_rects(i){
    var rec = records[i] 
    rec.canv_rect = rec.canvas.getBoundingClientRect();
    rec.i_rect = rec.image.getBoundingClientRect();
    rec.offsets = [ rec.i_rect.left - rec.canv_rect.left, rec.i_rect.top - rec.canv_rect.top ];
}

function make_mv(i){
    return function (event){
        onCanvasMV(event,i);
    }   
}

function make_md(i,mv){
    return function(event){
        if(records[i].draw){
            window.addEventListener("mousemove", mv, true);
            onCanvasMD(event,i);
        }
    }
}

function make_cs(i){
    return function(event){
        if(!records[i].draw){
            removeSpan(i,event);
        }
    }
}

function make_mu(i,mv){
    return function (event){
        window.removeEventListener("mousemove", mv, true);
        onCanvasMU(event,i);
    }
}

function make_de_click(i){
    return function(event){
        toggleDraw(i);
    }
}

function make_r_click(i){
    return function(event){
        ajax_update(i);
    }
}

var records = [];
for (var i = 0; i < bdinputs.length; i++){
    var record = {};
    record.canvas = document.getElementById("bd_in_"+i);
    record.image = record.canvas.querySelector("img");
    var ref_buttn = document.querySelector("#bd_in_"+i+" ~ div > input[type='button']");
    record.href = bdinputs[i]
    record.de_buttn = document.querySelector("#bd_in_"+i+" ~ div > input[type='button'] ~ input[type='button']");
    record.feedback = document.getElementById("bm_box_"+i);
    record.canv_rect = record.canvas.getBoundingClientRect();
    record.i_rect = record.image.getBoundingClientRect();
    record.offsets = [20,20];
    record.draw = true;
    record.dragging = null;
    record.root = null;
    record.dims = null;
    record.boxes = [];
    var existings = record.canvas.querySelectorAll("span");
    for (var j=0;j<existings.length;j++){
        var style = existings[j].style;
        var s_left = int(style.left.slice(0,-2)) - record.offsets[0];
        var s_top = int(style.top.slice(0,-2)) - record.offsets[1];
        var l_width = int(style.width.slice(0,-2));
        var l_height = int(style.height.slice(0,-2));
        existings[j].addEventListener("click",make_cs(i),true);
        record.boxes.push([ existings[j], s_top + "-" + s_left + "-" +  (s_top+l_height) + "-" + (s_left+l_width) ]);
    }
    
    record.image.ondragstart = function() { return false; };
    
    var mv = make_mv(i);
    var md = make_md(i,mv);
    var mu = make_mu(i,mv);
    var cde = make_de_click(i);
    var cr = make_r_click(i);
    record.canvas.addEventListener("mousedown", md, true);
    window.addEventListener("mouseup", mu);
    record.de_buttn.addEventListener("click", cde);
    ref_buttn.addEventListener("click", cr);
    
    records[i] = record;
    ajax_update(i);
}

window.addEventListener("scroll", update_all_rects);

function onCanvasMD(event,i){
    update_rects(i);
    var rec = records[i]
    var pt = get_rels(rec.canv_rect,event);
    rec.root = pt;
    rec.dragging = document.createElement("span");
    rec.dragging.addEventListener("click",make_cs(i),true);
    rec.canvas.appendChild(rec.dragging);
    rec.dragging.style.left = pt[0] +"px";
    rec.dragging.style.top = pt[1] + "px";
    rec.dims = [ pt[0], pt[1], 0, 0 ];
}

function onCanvasMV(event,i){
    var rec = records[i]
    var pt = get_rels(rec.canv_rect,event);
    var dims = get_rect(pt,rec.root);
    rec.dragging.style.left = dims[0] + "px";
    rec.dragging.style.top = dims[1] + "px";
    rec.dragging.style.width = dims[2] + "px";
    rec.dragging.style.height = dims[3] + "px";
    rec.dims = dims;
}

function onCanvasMU(event,i){
    var rec = records[i]
    if(rec.dragging == null){
        return;
    }
    var im_h = int(rec.i_rect.height);
    var im_w = int(rec.i_rect.width);
    if(rec.dims[2]==0||rec.dims[3]==0){
        rec.canvas.removeChild(rec.dragging);
    } else {
        var topy = clamp( 0, int(rec.dims[1] - rec.offsets[1]), im_h );
        var leftx = clamp( 0, int(rec.dims[0] - rec.offsets[0]), im_w );
        var bottomy = clamp( 0, int(rec.dims[1] + rec.dims[3] - rec.offsets[1]), im_h );
        var rightx = clamp( 0, int(rec.dims[0] + rec.dims[2] - rec.offsets[0]), im_w );
        if( topy!=bottomy && leftx!=rightx){
            addbox_ifuniq(i, rec.dragging, topy+"-"+leftx+"-"+bottomy+"-"+rightx);
        } else {
            rec.dragging.style.borderColor = "#FF0000";
        }
    }
    rec.dragging = null;
    console.log(rec.boxes);
}


function toggleDraw(i){
    var rec = records[i]
    var draw = !rec.draw
    rec.draw = draw
    rec.de_buttn.value = draw ? "Erase" : "Draw";
    if(rec.dragging!=null){
        rec.canvas.removeChild(rec.dragging);
        rec.dragging = null;
    }
    setboxpointer(rec.canvas, draw ? "" : "pointer");
    rec.canvas.style.cursor = draw ? "" : "auto";
}

function ajax_update(i){
    var rec = records[i];
    var n_box = rec.boxes.length;
    var dest = rec.href;
    var boxstring = "";
    if(n_box>0){
        dest += "?boxes=";
        for(var j=0;j<n_box;j++){
            boxstring += rec.boxes[j][1];
            if(j!=n_box-1){
                boxstring += "-";
            }
        }
    }
    rec.feedback.value = boxstring;
    loadDoc(dest+boxstring,rec.image);
}

function addbox_ifuniq(i, key, boxstring){
    var rec = records[i]
    var n_box = rec.boxes.length;
    for(var j=0;j<n_box;j++){
        if(rec.boxes[j][1]==boxstring){
            return false;
        }
    }
    rec.boxes.push([ key, boxstring ]);
    return true;
}

function removeSpan(i,event){
    for(var j=0;j<records[i].boxes.length;j++){
        if(records[i].boxes[j][0]==event.target){
            records[i].boxes.splice(j,1);
            break;
        }
    }
    records[i].canvas.removeChild(event.target);
}

function setboxpointer(canvas,style){
    var boxspans = canvas.querySelectorAll("span");
    for (var i=0;i<boxspans.length;i++){
        boxspans[i].style.cursor = style;
    }
}