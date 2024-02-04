document.addEventListener('DOMContentLoaded', (event) => {
    var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);
    var mediaRecorder;

    document.getElementById('recordButton').onclick = function() {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.ondataavailable = function(event) {
                    var reader = new FileReader();
                    reader.onloadend = function() {
                        var arrayBuffer = reader.result;
                        var bytes = new Uint8Array(arrayBuffer);
                        var base64String = btoa(String.fromCharCode.apply(null, bytes));
                        socket.emit('audio_chunk', base64String);
                    };
                    reader.readAsArrayBuffer(event.data);
                };
                mediaRecorder.start(100);
            })
            .catch(error => console.log(error));
    };
});
