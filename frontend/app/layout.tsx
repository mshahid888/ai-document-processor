import "./globals.css";

export const metadata = {
  title: "AI Document Processor (demo)",
  description: "Upload invoice PDFs → deterministic extraction → validation → xlsx export. Demo only.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
