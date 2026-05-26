import React from "react";
import ReactDOM from "react-dom/client";
import { createHashRouter, RouterProvider } from "react-router-dom";

import Gallery from "./pages/Gallery";
import Project from "./pages/Project";
import Convert from "./pages/Convert";
import Vectorize from "./pages/Vectorize";
import Settings from "./pages/Settings";
import Layout from "./Layout";
import "./styles.css";

const router = createHashRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Gallery /> },
      { path: "project/:id", element: <Project /> },
      { path: "project/:id/convert/:imageId", element: <Convert /> },
      { path: "project/:id/vectorize/:imageId", element: <Vectorize /> },
      { path: "settings", element: <Settings /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
