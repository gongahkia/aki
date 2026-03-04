use futures::task::noop_waker;
use std::future::Future;
use std::pin::Pin;
use std::task::{Context, Poll};
use tokio::task::{JoinError, JoinHandle};

pub fn poll_join_if_finished<T>(handle: &mut JoinHandle<T>) -> Option<Result<T, JoinError>> {
    if !handle.is_finished() {
        return None;
    }
    let waker = noop_waker();
    let mut cx = Context::from_waker(&waker);
    match Pin::new(handle).poll(&mut cx) {
        Poll::Ready(result) => Some(result),
        Poll::Pending => None,
    }
}

pub fn take_join_result_if_finished<T>(
    slot: &mut Option<JoinHandle<T>>,
) -> Option<Result<T, JoinError>> {
    let result = poll_join_if_finished(slot.as_mut()?)?;
    slot.take();
    Some(result)
}
