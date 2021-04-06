/* Adjust the aspect ratio to match the width */
function update_ar(event) {
	for(i=0;i<selectors.length;i++){
		var selector = selectors[i];
		var el = document.getElementById("gsel_"+selector.id);
		el.style.height = (el.getBoundingClientRect().width * selector.ar) + "px";
	}
}
/* OnClicks for table */
function select(selid,domel,x,y){
    var insel = document.getElementById("input_FOV_"+selid)
    domel.classList.toggle("selected");
    var op = insel.options.namedItem("selectcell_"+x+"_"+y)
    op.selected = !op.selected
}

/* Updates tables when collapsible is opened */
update_ar(null);
var buttons = document.querySelectorAll("button.collapsible");
for (var i = 0;i<buttons.length;i++){
	buttons[i].addEventListener("click",update_ar,false);
}