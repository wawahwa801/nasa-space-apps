import "./globals.css";

export const metadata = {
  title: "Project Dashboard",
  description: "Interactive project dashboard",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
