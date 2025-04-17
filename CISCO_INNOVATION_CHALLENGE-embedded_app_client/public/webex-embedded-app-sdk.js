// Placeholder for Webex Embedded App SDK
// Original: https://binaries.webex.com/static-content-widget/webex-embedded-app/webex-embedded-app-sdk.js

(function (window) {
  window.Webex = {
    EmbeddedAppSdk: function () {
      this.ready = () => Promise.resolve();
      this.getUser = () =>
        Promise.resolve({
          email: "user@sample.wbx.ai",
          displayName: "kicksco",
          profile: "logo.png",
        }); // 사용자 계
      this.getUser = () => Promise.resolve({ email: "admin@sample.wbx.ai" }); // 관리자 계정
    },
  };
})(window);
