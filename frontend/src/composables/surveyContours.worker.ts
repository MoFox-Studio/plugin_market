import { surveyContours } from './surveyContours';
import type { SurveyGeometryRequest, SurveyGeometryResult } from './surveyGeometry';

const scope = self as unknown as {
  onmessage: (event: MessageEvent<SurveyGeometryRequest>) => void;
  postMessage(result: SurveyGeometryResult): void;
};
scope.onmessage = ({ data }) => {
  scope.postMessage({ ...data, geometry: surveyContours(data.sheet) });
};
