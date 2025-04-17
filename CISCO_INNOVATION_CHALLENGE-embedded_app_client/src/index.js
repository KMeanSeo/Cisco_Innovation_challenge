import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import AdminApp from "./scripts/Admin";
import User from "./scripts/User";
import UserDetail from "./scripts/UserDetail";

const root = ReactDOM.createRoot(document.getElementById("root"));

const App = ({ user }) => {
  return (
    <HashRouter>
      <Routes>
        {/* 기본 경로: 일반 사용자 */}
        <Route path="/" element={<User user={user} />} />
        {/* 관리자 전용 경로 */}
        <Route path="/admin" element={<AdminApp user={user} />} />
        {/* 기타 상세 페이지 등 */}
        <Route path="/detail" element={<UserDetail />} />
        {/* 알 수 없는 경로는 기본 경로로 리다이렉션 */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </HashRouter>
  );
};

const init = async () => {
  if (window.Webex?.EmbeddedAppSdk) {
    const webex = new window.Webex.EmbeddedAppSdk();
    try {
      await webex.ready();
      const user = await webex.getUser();
      console.log("Webex 로그인 사용자:", user);
      // 사용자 정보와 함께 App 컴포넌트를 렌더링
      root.render(<App user={user} />);
    } catch (e) {
      console.error("❌ 초기화 실패:", e);
      root.render(<div>Webex 사용자 정보를 불러올 수 없습니다.</div>);
    }
  } else {
    root.render(<div>Webex SDK가 로드되지 않았습니다.</div>);
  }
};

init();
