import { useLocation, useNavigate } from "react-router-dom";

function UserDetail() {
  const location = useLocation();
  const navigate = useNavigate(); // ✅ 추가
  const user = location.state?.user;

  if (!user) {
    return <div style={{ padding: "2rem" }}>사용자 정보가 없습니다.</div>;
  }

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        height: "100vh",
        background: "linear-gradient(135deg, #e0f7fa, #ffffff)",
      }}
    >
      <div
        style={{
          backgroundColor: "#fff",
          padding: "2rem",
          borderRadius: "12px",
          boxShadow: "0 4px 20px rgba(0,0,0,0.1)",
          maxWidth: "400px",
          width: "90%",
          textAlign: "center",
          fontFamily: "Arial, sans-serif",
          transition: "transform 0.2s ease-in-out",
        }}
      >
        <img
          src={`/kicksco_embedded_app/${user.profile || "user_icon.png"}`}
          alt="사용자 이미지"
          style={{
            width: "100px",
            height: "100px",
            borderRadius: "50%",
            objectFit: "cover",
            marginBottom: "1rem",
            border: "3px solid #007bff",
          }}
        />
        <h2 style={{ color: "#007bff", marginBottom: "0.5rem" }}>
          👤 {user.displayName ?? "이름 없음"}
        </h2>
        <p style={{ fontSize: "1rem", marginBottom: "0.3rem" }}>
          <strong>📧 이메일:</strong> {user.email}
        </p>
        <p style={{ fontSize: "1rem", marginBottom: "1.5rem" }}>
          <strong>🎁 리워드:</strong> {user.reward ?? 0} 포인트
        </p>

        {/* 👇 뒤로 가기 버튼 추가 */}
        <button
          onClick={() => navigate(-1)}
          style={{
            padding: "0.5rem 1rem",
            backgroundColor: "#007bff",
            color: "#fff",
            border: "none",
            borderRadius: "5px",
            fontWeight: "bold",
            cursor: "pointer",
          }}
        >
          돌아가기
        </button>
      </div>
    </div>
  );
}

export default UserDetail;
