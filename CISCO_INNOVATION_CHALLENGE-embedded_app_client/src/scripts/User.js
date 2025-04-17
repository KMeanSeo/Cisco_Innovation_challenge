import React, { useRef, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Webcam from 'react-webcam';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import '../css/User.css';

const API_BASE_URL = 'https://noble-tammara-kicksco-97f46231.koyeb.app';

function User({ user }) {
    const [mode, setMode] = useState('return');
    const [selectedImage, setSelectedImage] = useState(null);
    const [coords, setCoords] = useState({ latitude: '', longitude: '' });
    const [requests, setRequests] = useState([]);
    const [useWebcam, setUseWebcam] = useState(false);
    const [modalMessage, setModalMessage] = useState('');
    const [reward, setReward] = useState(user?.reward ?? 0);

    const webcamRef = useRef(null);
    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const navigate = useNavigate();
    const email = user?.email || '';

    // 위치 정보 가져오기
    const getCurrentLocation = () => {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                toast.error('위치 정보 사용이 불가능합니다.');
                return reject(new Error('Geolocation not supported'));
            }
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const location = {
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude
                    };
                    setCoords(location);
                    resolve(location);
                },
                (err) => {
                    console.error('위치 정보 오류:', err);
                    toast.error('위치 정보를 가져오지 못했습니다.');
                    reject(err);
                }
            );
        });
    };

    // adjust 모드이면 위치 정보 자동 갱신
    useEffect(() => {
        if (mode === 'adjust') {
            getCurrentLocation();
        }
    }, [mode]);

    // 요청 목록 주기적 조회
    useEffect(() => {
        const interval = setInterval(fetchRequests, 10000);
        return () => clearInterval(interval);
    }, []);

    const fetchRequests = async () => {
        try {
            const webex = new window.Webex.EmbeddedAppSdk();
            await webex.ready();
            const { spaceId } = await webex.getSpaceId();
            const res = await fetch(`${API_BASE_URL}/api/requests?roomId=${spaceId}`);
            const data = await res.json();
            setRequests(data);
        } catch (err) {
            console.error('요청 목록 조회 실패:', err);
        }
    };

    // 카메라 캡처
    const handleCapture = () => {
        const screenshot = webcamRef.current.getScreenshot();
        if (screenshot) {
            const byteString = atob(screenshot.split(',')[1]);
            const mimeString = screenshot.split(',')[0].split(':')[1].split(';')[0];
            const ab = new ArrayBuffer(byteString.length);
            const ia = new Uint8Array(ab);
            for (let i = 0; i < byteString.length; i++) {
                ia[i] = byteString.charCodeAt(i);
            }
            const blob = new Blob([ab], { type: mimeString });
            const file = new File([blob], 'captured.jpg', { type: mimeString });
            setSelectedImage(file);
            setUseWebcam(false);
        }
    };

    const handleRetake = () => {
        setSelectedImage(null);
        setUseWebcam(false);
    };

    // 데이터 전송 처리 (반납, 위치 조정)
    const handleSubmit = async () => {
        if (!email) return toast.error('이메일 정보가 없습니다.');
        if (!selectedImage) return toast.error('이미지를 선택해주세요.');

        try {
            const location = await getCurrentLocation();
            const formData = new FormData();
            formData.append('email', email);
            formData.append('latitude', location.latitude);
            formData.append('longitude', location.longitude);
            formData.append('image', selectedImage);
            formData.append('timestamp', new Date().toISOString());
            formData.append('lat', location.latitude);
            formData.append('lng', location.longitude);

            const url = mode === 'return'
                ? `${API_BASE_URL}/api/return`
                : `${API_BASE_URL}/api/pm-adjusted`;

            const res = await fetch(url, {
                method: 'POST',
                body: formData
            });
            if (!res.ok) throw new Error();
            toast.success(mode === 'return'
                ? '반납 알림이 전송되었습니다!'
                : '조정 내용이 전송되었습니다!');
        } catch (err) {
            console.error(err);
            toast.error(mode === 'return' ? '반납 요청 실패' : '조정 내용 전송 실패');
        }
    };

    const handleFileSelect = (e) => {
        const file = e.target.files[0];
        if (file) setSelectedImage(file);
    };

    return (
        <div className="user-wrapper">
            <ToastContainer />

            <header className="user-header">
                <img
                    className="user-logo"
                    src="/kicksco_embedded_app/logo.png"
                    alt="KickSco 로고"
                />
                <button
                    className="user-icon-button"
                    onClick={() => navigate('/detail', { state: { user } })}
                >
                    <img
                        className="user-icon"
                        src="/kicksco_embedded_app/user_icon.png"
                        alt="User"
                    />
                </button>
            </header>

            <div className="user-info">
                <div>
                    <label> 사용자 : </label> <span>{email}</span>
                </div>
                <div className="user-mode-buttons">
                    <button
                        onClick={() => setMode('return')}
                        className={`user-mode-button ${mode === 'return' ? 'active' : 'inactive'}`}
                    >
                        PM 반납
                    </button>
                    <button
                        onClick={() => setMode('adjust')}
                        className={`user-mode-button ${mode === 'adjust' ? 'active' : 'inactive'}`}
                    >
                        PM 위치 조정
                    </button>
                </div>
            </div>

            <div className="video-container">
                {!selectedImage && (
                    <>
                        <Webcam
                            ref={webcamRef}
                            audio={false}
                            screenshotFormat="image/jpeg"
                            videoConstraints={{
                                facingMode: 'environment',
                                width: { ideal: 1280 },
                                height: { ideal: 720 }
                            }}
                            className="video-player"
                        />
                        <img
                            src="/kicksco_embedded_app/img.png"
                            onClick={handleCapture}
                            className="capture-button"
                            alt="캡처"
                        />
                    </>
                )}

                {selectedImage && (
                    <div className="selected-image-container">
                        <img
                            src={URL.createObjectURL(selectedImage)}
                            alt="Captured"
                            className="selected-image"
                        />
                        <button onClick={handleRetake} className="retake-button">
                            재촬영
                        </button>
                    </div>
                )}

                <canvas ref={canvasRef} width="320" height="240" style={{ display: 'none' }} />
            </div>

            {mode === 'adjust' && requests.length > 0 && (
                <div className="user-request-list">
                    <h4>조정 요청 목록</h4>
                    <ul>
                        {requests.map((req, idx) => (
                            <li key={idx}>{req.text}</li>
                        ))}
                    </ul>
                </div>
            )}

            <button onClick={handleSubmit} className="user-submit-button">
                전송
            </button>
        </div>
    );
}

export default User;