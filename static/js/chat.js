// Global objects
var speechRecognizer;
var avatarSynthesizer;
var peerConnection;
var messages = [];
var messageInitiated = false;
var dataSources = [];
var sentenceLevelPunctuations = ['.', '?', '!', ':', ';', '。', '？', '！', '：', '；'];
var enableDisplayTextAlignmentWithSpeech = true;
var enableQuickReply = false;
var quickReplies = ['Let me take a look.', 'Let me check.', 'One moment, please.'];
var byodDocRegex = new RegExp(/\[doc(\d+)\]/g);
var isSpeaking = false;
var spokenTextQueue = [];
var sessionActive = false;
var lastSpeakTime;
var imgUrl = "";

const scenarioPrompts = {};
const selectedScenario={};

async function fetchPrompt() {
    const selectedScenario = document.getElementById('scenarioSelect').value;
    const response = await fetch("/get_prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario_id: selectedScenario })
    });
    const data = await response.json();

    // Display the entire response data in the console
    console.log(data);

    // If your response contains a specific field, say "scenario",
    // you can log that field too:
    // console.log(data.scenario);
    scenarioPrompts[selectedScenario] = data;

}


// Connect to avatar service
function connectAvatar() {
    const cogSvcRegion = "southeastasia";
    const cogSvcSubKey = "d21a028b925c4d4f84cff3796ecad2ac";

    let speechSynthesisConfig = SpeechSDK.SpeechConfig.fromSubscription(cogSvcSubKey, cogSvcRegion);

    const talkingAvatarCharacter = "lisa";
    const talkingAvatarStyle = "casual-sitting";
    const avatarConfig = new SpeechSDK.AvatarConfig(talkingAvatarCharacter, talkingAvatarStyle);
    avatarSynthesizer = new SpeechSDK.AvatarSynthesizer(speechSynthesisConfig, avatarConfig);

    avatarSynthesizer.avatarEventReceived = function (s, e) {
        console.log("Event received: " + e.description + (e.offset === 0 ? "" : ", offset from session start: " + e.offset / 10000 + "ms."));
    };

    // Configure speech recognition with selected language
    const selectedLanguage = document.getElementById('languageSelect').value;
    const speechRecognitionConfig = SpeechSDK.SpeechConfig.fromEndpoint(
        new URL(`wss://${cogSvcRegion}.stt.speech.microsoft.com/speech/universal/v2`),
        cogSvcSubKey
    );
    
    speechRecognitionConfig.setProperty(
        SpeechSDK.PropertyId.SpeechServiceConnection_LanguageIdMode,
        "Continuous"
    );
    
    const autoDetectSourceLanguageConfig = SpeechSDK.AutoDetectSourceLanguageConfig.fromLanguages([selectedLanguage]);
    speechRecognizer = SpeechSDK.SpeechRecognizer.FromConfig(
        speechRecognitionConfig,
        autoDetectSourceLanguageConfig,
        SpeechSDK.AudioConfig.fromDefaultMicrophoneInput()
    );

    // Only initialize messages once
    if (!messageInitiated) {
        initMessages();
        messageInitiated = true;
    }

    document.getElementById('startSession').disabled = true;
    document.getElementById('configuration').hidden = true;

    const xhr = new XMLHttpRequest();
    xhr.open("GET", `https://${cogSvcRegion}.tts.speech.microsoft.com/cognitiveservices/avatar/relay/token/v1`);
    xhr.setRequestHeader("Ocp-Apim-Subscription-Key", cogSvcSubKey);
    xhr.addEventListener("readystatechange", function() {
        if (this.readyState === 4) {
            const responseData = JSON.parse(this.responseText);
            setupWebRTC(
                responseData.Urls[0],
                responseData.Username,
                responseData.Password
            );
        }
    });
    xhr.send();
}

// Initialize messages with selected scenario


function initMessages() {
    messages = [];
    const systemMessage = {
        role: 'system',
        content: scenarioPrompts[selectedScenario]
    };
    messages.push(systemMessage);
}
// Setup WebRTC
function setupWebRTC(iceServerUrl, iceServerUsername, iceServerCredential) {
    peerConnection = new RTCPeerConnection({
        iceServers: [{
            urls: [iceServerUrl],
            username: iceServerUsername,
            credential: iceServerCredential
        }]
    });

    peerConnection.ontrack = function (event) {
        if (event.track.kind === 'audio') {
            let audioElement = document.createElement('audio');
            audioElement.id = 'audioPlayer';
            audioElement.srcObject = event.streams[0];
            audioElement.autoplay = true;

            audioElement.onplaying = () => {
                console.log(`WebRTC ${event.track.kind} channel connected.`);
            };

            // Clean up existing audio element if there is any
            let remoteVideoDiv = document.getElementById('remoteVideo');
            for (var i = 0; i < remoteVideoDiv.childNodes.length; i++) {
                if (remoteVideoDiv.childNodes[i].localName === event.track.kind) {
                    remoteVideoDiv.removeChild(remoteVideoDiv.childNodes[i]);
                }
            }

            document.getElementById('remoteVideo').appendChild(audioElement);
        }

        if (event.track.kind === 'video') {
            let videoElement = document.createElement('video');
            videoElement.id = 'videoPlayer';
            videoElement.srcObject = event.streams[0];
            videoElement.autoplay = true;
            videoElement.playsInline = true;

            videoElement.onplaying = () => {
                document.getElementById('loaderContainer').style.display = 'none';
                let remoteVideoDiv = document.getElementById('remoteVideo');
                for (var i = 0; i < remoteVideoDiv.childNodes.length; i++) {
                    if (remoteVideoDiv.childNodes[i].localName === event.track.kind) {
                        remoteVideoDiv.removeChild(remoteVideoDiv.childNodes[i]);
                    }
                }

                document.getElementById('remoteVideo').appendChild(videoElement);
                console.log(`WebRTC ${event.track.kind} channel connected.`);
                document.getElementById('microphone').disabled = false;
                document.getElementById('stopSession').disabled = false;
                document.getElementById('remoteVideo').style.width = '960px';
                document.getElementById('chatHistory').hidden = false;
                document.getElementById('showTypeMessage').disabled = false;
                document.getElementById('localVideo').hidden = true;
                
                if (lastSpeakTime === undefined) {
                    lastSpeakTime = new Date();
                }

                setTimeout(() => { sessionActive = true; }, 5000);
            };
        }
    };

    peerConnection.addEventListener("datachannel", event => {
        const dataChannel = event.channel;
        dataChannel.onmessage = e => {
            console.log(`[${new Date().toISOString()}] WebRTC event received: ${e.data}`);
        };
    });

    const c = peerConnection.createDataChannel("eventChannel");

    peerConnection.oniceconnectionstatechange = e => {
        console.log("WebRTC status: " + peerConnection.iceConnectionState);
        if (peerConnection.iceConnectionState === 'disconnected') {
            // document.getElementById('localVideo').hidden = false;
            document.getElementById('remoteVideo').style.width = '0.1px';
        }
    };

    peerConnection.addTransceiver('video', { direction: 'sendrecv' });
    peerConnection.addTransceiver('audio', { direction: 'sendrecv' });

    avatarSynthesizer.startAvatarAsync(peerConnection).then((r) => {
        if (r.reason === SpeechSDK.ResultReason.SynthesizingAudioCompleted) {
            console.log(`[${new Date().toISOString()}] Avatar started. Result ID: ${r.resultId}`);
        } else {
            console.log(`[${new Date().toISOString()}] Unable to start avatar. Result ID: ${r.resultId}`);
            if (r.reason === SpeechSDK.ResultReason.Canceled) {
                let cancellationDetails = SpeechSDK.CancellationDetails.fromResult(r);
                if (cancellationDetails.reason === SpeechSDK.CancellationReason.Error) {
                    console.log(cancellationDetails.errorDetails);
                }
                console.log("Unable to start avatar: " + cancellationDetails.errorDetails);
            }
            document.getElementById('startSession').disabled = false;
            document.getElementById('configuration').hidden = false;
        }
    }).catch((error) => {
        console.log(`[${new Date().toISOString()}] Avatar failed to start. Error: ${error}`);
        document.getElementById('startSession').disabled = false;
        document.getElementById('configuration').hidden = false;
    });
}
//....................................................................
function handleUserQuery(userQuery, userQueryHTML, imgUrlPath) {
    let contentMessage = userQuery;
    autoStopMicrophone();
    if (imgUrlPath.trim()) {
        contentMessage = [
            {
                "type": "text",
                "text": userQuery
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": imgUrlPath
                }
            }
        ];
    }

    let chatMessage = {
        role: 'user',
        content: contentMessage
    };

    messages.push(chatMessage);
    let chatHistoryTextArea = document.getElementById('chatHistory');
    if (chatHistoryTextArea.innerHTML !== '' && !chatHistoryTextArea.innerHTML.endsWith('\n\n')) {
        chatHistoryTextArea.innerHTML += '\n\n';
    }

    chatHistoryTextArea.innerHTML += imgUrlPath.trim() ? "<br/><br/>User: " + userQueryHTML : "<br/><br/>User: " + userQuery + "<br/>";
    chatHistoryTextArea.scrollTop = chatHistoryTextArea.scrollHeight;

    // Stop previous speaking if there is any
    if (isSpeaking) {
        stopSpeaking();
    }

    const azureOpenAIEndpoint = "https://gmr-innovex.openai.azure.com/";
    const azureOpenAIApiKey = "BiRKNCm2kMK1sslaFQPpG8hiRfWvL10DrFP0u3h7IeN402rOwVoQJQQJ99AKAC77bzfXJ3w3AAABACOGJVKo";
    const azureOpenAIDeploymentName = "gpt-4o";

    let url = `${azureOpenAIEndpoint}/openai/deployments/${azureOpenAIDeploymentName}/chat/completions?api-version=2023-06-01-preview`;
    let body = JSON.stringify({
        messages: messages,
        stream: true
    });

    if (dataSources.length > 0) {
        url = `${azureOpenAIEndpoint}/openai/deployments/${azureOpenAIDeploymentName}/extensions/chat/completions?api-version=2023-06-01-preview`;
        body = JSON.stringify({
            dataSources: dataSources,
            messages: messages,
            stream: true
        });
    }

    let assistantReply = '';
    let toolContent = '';
    let spokenSentence = '';
    let displaySentence = '';

    fetch(url, {
        method: 'POST',
        headers: {
            'api-key': azureOpenAIApiKey,
            'Content-Type': 'application/json'
        },
        body: body
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Chat API response status: ${response.status} ${response.statusText}`);
        }

        let chatHistoryTextArea = document.getElementById('chatHistory');
        chatHistoryTextArea.innerHTML += imgUrlPath.trim() ? 'Assistant: ' : '<br/>Assistant: ';

        const reader = response.body.getReader();

        // Function to recursively read chunks from the stream
        function read(previousChunkString = '') {
            return reader.read().then(({ value, done }) => {
                if (done) {
                    return;
                }

                let chunkString = new TextDecoder().decode(value, { stream: true });
                if (previousChunkString !== '') {
                    chunkString = previousChunkString + chunkString;
                }

                if (!chunkString.endsWith('}\n\n') && !chunkString.endsWith('[DONE]\n\n')) {
                    return read(chunkString);
                }

                chunkString.split('\n\n').forEach((line) => {
                    try {
                        if (line.startsWith('data:') && !line.endsWith('[DONE]')) {
                            const responseJson = JSON.parse(line.substring(5).trim());
                            let responseToken = undefined;
                            if (dataSources.length === 0) {
                                responseToken = responseJson.choices[0].delta.content;
                            } else {
                                let role = responseJson.choices[0].messages[0].delta.role;
                                if (role === 'tool') {
                                    toolContent = responseJson.choices[0].messages[0].delta.content;
                                } else {
                                    responseToken = responseJson.choices[0].messages[0].delta.content;
                                    if (responseToken !== undefined) {
                                        if (byodDocRegex.test(responseToken)) {
                                            responseToken = responseToken.replace(byodDocRegex, '').trim();
                                        }

                                        if (responseToken === '[DONE]') {
                                            responseToken = undefined;
                                        }
                                    }
                                }
                            }

                            if (responseToken !== undefined && responseToken !== null) {
                                assistantReply += responseToken;
                                displaySentence += responseToken;

                                if (responseToken === '\n' || responseToken === '\n\n') {
                                    spokenSentence += responseToken;
                                    speak(spokenSentence);
                                    spokenSentence = '';
                                } else {
                                    spokenSentence += responseToken;

                                    responseToken = responseToken.replace(/\n/g, '');
                                    if (responseToken.length === 1 || responseToken.length === 2) {
                                        for (let i = 0; i < sentenceLevelPunctuations.length; ++i) {
                                            let sentenceLevelPunctuation = sentenceLevelPunctuations[i];
                                            if (responseToken.startsWith(sentenceLevelPunctuation)) {
                                                speak(spokenSentence);
                                                spokenSentence = '';
                                                break;
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    } catch (error) {
                        console.log(`Error occurred while parsing the response: ${error}`);
                        console.log(chunkString);
                    }
                });

                if (!enableDisplayTextAlignmentWithSpeech) {
                    chatHistoryTextArea.innerHTML += displaySentence.replace(/\n/g, '<br/>');
                    chatHistoryTextArea.scrollTop = chatHistoryTextArea.scrollHeight;
                    displaySentence = '';
                }

                return read();
            });
        }

        return read();
    })
    .then(() => {
        if (spokenSentence !== '') {
            speak(spokenSentence);
            spokenSentence = '';
        }

        if (dataSources.length > 0) {
            let toolMessage = {
                role: 'tool',
                content: toolContent
            };
            messages.push(toolMessage);
        }

        let assistantMessage = {
            role: 'assistant',
            content: assistantReply
        };
        messages.push(assistantMessage);
    });
}

// HTML encoding helper
function htmlEncode(text) {
    const entityMap = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
        '/': '&#x2F;'
    };
    return String(text).replace(/[&<>"'\/]/g, (match) => entityMap[match]);
}

// Speech functions
function speak(text, endingSilenceMs = 0) {
    if (isSpeaking) {
        spokenTextQueue.push(text);
        return;
    }
    speakNext(text, endingSilenceMs);
}

function speakNext(text, endingSilenceMs = 0) {
    // Auto stop mic when avatar starts speaking
    if (document.getElementById('microphone').innerHTML === 'Stop Microphone') {
        speechRecognizer.stopContinuousRecognitionAsync(
            () => {
                document.getElementById('microphone').innerHTML = 'Start Microphone';
                console.log("Auto-stopped microphone for avatar speech");
            },
            (err) => {
                console.log("Failed to auto-stop recognition:", err);
            }
        );
    }
    
    const selectedLanguage = document.getElementById('languageSelect').value;
    let ttsVoice = "en-US-AvaMultilingualNeural";
    
    // Map language to appropriate voice
    switch(selectedLanguage) {
        case "hi-IN":
            ttsVoice = "hi-IN-SwaraNeural";
            break;
        case "te-IN":
            ttsVoice = "te-IN-ShrutiNeural";
            break;
        case "ta-IN":
            ttsVoice = "ta-IN-PallaviNeural";
            break;
        case "kn-IN":
            ttsVoice = "kn-IN-SapnaNeural";
            break;
    }

    let ssml = `<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='${selectedLanguage}'>
        <voice name='${ttsVoice}'>
            <mstts:ttsembedding>
                <mstts:leadingsilence-exact value='0'/>${htmlEncode(text)}
            </mstts:ttsembedding>
        </voice>
    </speak>`;

    if (endingSilenceMs > 0) {
        ssml = ssml.replace('</mstts:ttsembedding>', `<break time='${endingSilenceMs}ms' /></mstts:ttsembedding>`);
    }

    if (enableDisplayTextAlignmentWithSpeech) {
        let chatHistoryTextArea = document.getElementById('chatHistory');
        chatHistoryTextArea.innerHTML += text.replace(/\n/g, '<br/>');
        chatHistoryTextArea.scrollTop = chatHistoryTextArea.scrollHeight;
    }

    lastSpeakTime = new Date();
    isSpeaking = true;
    document.getElementById('stopSpeaking').disabled = false;

    avatarSynthesizer.speakSsmlAsync(ssml)
        .then((result) => {
            if (result.reason === SpeechSDK.ResultReason.SynthesizingAudioCompleted) {
                console.log(`Speech synthesized to speaker for text [ ${text} ]. Result ID: ${result.resultId}`);
                lastSpeakTime = new Date();

                // Auto start mic after avatar finishes speaking if no more text in queue
                if (spokenTextQueue.length === 0) {
                    setTimeout(() => {
                        if (!document.getElementById('microphone').disabled && !isSpeaking) {
                            speechRecognizer.startContinuousRecognitionAsync(
                                () => {
                                    document.getElementById('microphone').innerHTML = 'Stop Microphone';
                                    console.log("Auto-started microphone after avatar speech");
                                },
                                (err) => {
                                    console.log("Failed to auto-start recognition:", err);
                                }
                            );
                        }
                    }, 1000); // Small delay before activating mic
                }
            } else {
                console.log(`Error occurred while speaking the SSML. Result ID: ${result.resultId}`);
            }

            if (spokenTextQueue.length > 0) {
                speakNext(spokenTextQueue.shift());
            } else {
                isSpeaking = false;
                document.getElementById('stopSpeaking').disabled = true;
            }
        })
        .catch((error) => {
            console.log(`Error occurred while speaking the SSML: [ ${error} ]`);
            if (spokenTextQueue.length > 0) {
                speakNext(spokenTextQueue.shift());
            } else {
                isSpeaking = false;
                document.getElementById('stopSpeaking').disabled = true;
            }
        });
}

///............................................................

function stopSpeaking() {
    spokenTextQueue = [];
    avatarSynthesizer.stopSpeakingAsync()
        .then(() => {
            isSpeaking = false;
            document.getElementById('stopSpeaking').disabled = true;
            console.log(`[${new Date().toISOString()}] Stop speaking request sent.`);
        })
        .catch((error) => {
            console.log("Error occurred while stopping speaking: " + error);
        });
}

function autoStartMicrophone() {
    if (!document.getElementById('microphone').disabled) {
        document.getElementById('microphone').innerHTML = 'Stop Microphone';
        speechRecognizer.startContinuousRecognitionAsync(
            () => {
                console.log("Auto-started microphone");
            },
            (err) => {
                console.log("Failed to auto-start recognition:", err);
            }
        );
    }
}

function autoStopMicrophone() {
    if (document.getElementById('microphone').innerHTML === 'Stop Microphone') {
        speechRecognizer.stopContinuousRecognitionAsync(
            () => {
                document.getElementById('microphone').innerHTML = 'Start Microphone';
                console.log("Auto-stopped microphone");
            },
            (err) => {
                console.log("Failed to auto-stop recognition:", err);
            }
        );
    }
}


window.startSession = async () => {
    document.getElementById('loaderContainer').style.display = 'flex';
    await fetchPrompt();
    connectAvatar();
};


window.stopSession = () => {
    document.getElementById('startSession').disabled = false;
    document.getElementById('microphone').disabled = true;
    document.getElementById('stopSession').disabled = true;
    document.getElementById('configuration').hidden = false;
    document.getElementById('chatHistory').hidden = true;
    document.getElementById('showTypeMessage').checked = false;
    document.getElementById('showTypeMessage').disabled = true;
    document.getElementById('userMessageBox').hidden = true;
    document.getElementById('uploadImgIcon').hidden = true;
    // document.getElementById('localVideo').hidden = true;

    disconnectAvatar();
};

window.clearChatHistory = () => {
    document.getElementById('chatHistory').innerHTML = '';
    initMessages();
};

window.microphone = () => {
    if (document.getElementById('microphone').innerHTML === 'Stop Microphone') {
        document.getElementById('microphone').disabled = true;
        speechRecognizer.stopContinuousRecognitionAsync(
            () => {
                document.getElementById('microphone').innerHTML = 'Start Microphone';
                document.getElementById('microphone').disabled = false;
            },
            (err) => {
                console.log("Failed to stop continuous recognition:", err);
                document.getElementById('microphone').disabled = false;
            }
        );
        return;
    }

    document.getElementById('audioPlayer')?.play();
    
    document.getElementById('microphone').disabled = true;
    speechRecognizer.recognized = async (s, e) => {
        if (e.result.reason === SpeechSDK.ResultReason.RecognizedSpeech) {
            let userQuery = e.result.text.trim();
            if (userQuery === '') {
                return;
            }

            document.getElementById('microphone').disabled = true;
            speechRecognizer.stopContinuousRecognitionAsync(
                () => {
                    document.getElementById('microphone').innerHTML = 'Start Microphone';
                    document.getElementById('microphone').disabled = false;
                },
                (err) => {
                    console.log("Failed to stop continuous recognition:", err);
                    document.getElementById('microphone').disabled = false;
                }
            );

            handleUserQuery(userQuery, "", "");
        }
    };

    speechRecognizer.startContinuousRecognitionAsync(
        () => {
            document.getElementById('microphone').innerHTML = 'Stop Microphone';
            document.getElementById('microphone').disabled = false;
        },
        (err) => {
            console.log("Failed to start continuous recognition:", err);
            document.getElementById('microphone').disabled = false;
        }
    );
};

window.updateTypeMessageBox = () => {
    if (document.getElementById('showTypeMessage').checked) {
        document.getElementById('userMessageBox').hidden = false;
        document.getElementById('uploadImgIcon').hidden = false;
        document.getElementById('userMessageBox').addEventListener('keyup', (e) => {
            if (e.key === 'Enter') {
                const userQuery = document.getElementById('userMessageBox').innerText;
                const messageBox = document.getElementById('userMessageBox');
                const childImg = messageBox.querySelector("#picInput");
                if (childImg) {
                    childImg.style.width = "200px";
                    childImg.style.height = "200px";
                }
                let userQueryHTML = messageBox.innerHTML.trim();
                if (userQueryHTML.startsWith('<img')) {
                    userQueryHTML = "<br/>" + userQueryHTML;
                }
                if (userQuery !== '') {
                    handleUserQuery(userQuery.trim(), userQueryHTML, imgUrl);
                    document.getElementById('userMessageBox').innerHTML = '';
                    imgUrl = "";
                }
            }
        });

        document.getElementById('uploadImgIcon').addEventListener('click', function() {
            imgUrl = "https://wallpaperaccess.com/full/528436.jpg";
            const userMessage = document.getElementById("userMessageBox");
            const childImg = userMessage.querySelector("#picInput");
            if (childImg) {
                userMessage.removeChild(childImg);
            }
            userMessage.innerHTML += '<br/><img id="picInput" src="https://wallpaperaccess.com/full/528436.jpg" style="width:100px;height:100px"/><br/><br/>';
        });
    } else {
        document.getElementById('userMessageBox').hidden = true;
        document.getElementById('uploadImgIcon').hidden = true;
        imgUrl = "";
    }
};

// Language and scenario change handlers
document.getElementById('languageSelect')?.addEventListener('change', () => {
    if (sessionActive) {
        const shouldReconnect = confirm("Changing language requires reconnecting. Continue?");
        if (shouldReconnect) {
            window.stopSession();
            window.startSession();
        }
    }
});

document.getElementById('scenarioSelect')?.addEventListener('change', () => {
    if (sessionActive) {
        const shouldRestart = confirm("Changing scenario will restart the conversation. Continue?");
        if (shouldRestart) {
            window.clearChatHistory();
        }
    }
});

// Initialize on page load
window.onload = () => {
    setInterval(() => {
        if (sessionActive) {
            // Check video stream state
            let videoElement = document.getElementById('videoPlayer');
            if (videoElement !== null && videoElement !== undefined) {
                let videoTime = videoElement.currentTime;
                setTimeout(() => {
                    if (videoElement.currentTime === videoTime && sessionActive) {
                        sessionActive = false;
                        console.log(`[${new Date().toISOString()}] Video stream disconnected, reconnecting...`);
                        connectAvatar();
                    }
                }, 2000);
            }

            // Check for idle state
            if (lastSpeakTime) {
                let currentTime = new Date();
                if (currentTime - lastSpeakTime > 15000 && sessionActive && !isSpeaking) {
                    document.getElementById('localVideo').hidden = false;
                    document.getElementById('remoteVideo').style.width = '0.1px';
                    sessionActive = false;
                }
            }
        }
    }, 2000);
};

// Cleanup on window unload
window.addEventListener('unload', () => {
    if (avatarSynthesizer) {
        avatarSynthesizer.close();
    }
    if (speechRecognizer) {
        speechRecognizer.close();
    }
    sessionActive = false;
});

// Error handler
window.onerror = function(msg, url, lineNo, columnNo, error) {
    console.error('Error: ', msg, '\nURL: ', url, '\nLine: ', lineNo, '\nColumn: ', columnNo, '\nError object: ', error);
    return false;
};
