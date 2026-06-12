import client from "./client";
import { Instructor } from "../types/instructor";

export async function fetchInstructor(name: string): Promise<Instructor> {
  const resp = await client.get(`/api/instructors/${encodeURIComponent(name)}`);
  return resp.data;
}
