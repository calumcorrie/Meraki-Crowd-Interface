var img = document.getElementById("portal");
var nop = 0

var ticker;

function reloadImage(){
    curr = img.src;
    path = curr.slice(0,curr.lastIndexOf("/")+1);
    img.src = path + (++nop);
}

function start(){
    stop();
    reloadImage();
    ticker = setInterval(reloadImage,15000);
}

function stop(){
    clearInterval(ticker);
}

start();