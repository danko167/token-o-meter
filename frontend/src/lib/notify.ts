import { notifications } from '@mantine/notifications';

type NotifyOptions = {
  title: string;
  message?: string;
};

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Something went wrong.';
}

export function notifySuccess({ title, message }: NotifyOptions) {
  notifications.show({
    color: 'green',
    title,
    message,
    autoClose: 4500,
  });
}

export function notifyWarning({ title, message }: NotifyOptions) {
  notifications.show({
    color: 'yellow',
    title,
    message,
    autoClose: 8000,
  });
}

export function notifyError(title: string, error: unknown) {
  notifications.show({
    color: 'red',
    title,
    message: errorMessage(error),
    autoClose: 9000,
  });
}
