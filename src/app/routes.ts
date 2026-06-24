import { createBrowserRouter } from "react-router";
import { ClientHome } from "./components/ClientHome";
import { ClientRequest } from "./components/ClientRequest";
import { TrackingView } from "./components/TrackingView";
import { ServiceDashboard } from "./components/ServiceDashboard";
import { RequestDetails } from "./components/RequestDetails";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: ClientHome,
  },
  {
    path: "/request",
    Component: ClientRequest,
  },
  {
    path: "/tracking/:requestId",
    Component: TrackingView,
  },
  {
    path: "/service",
    Component: ServiceDashboard,
  },
  {
    path: "/service/:requestId",
    Component: RequestDetails,
  },
]);
